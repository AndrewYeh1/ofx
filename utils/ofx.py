import pandas as pd
import re

def clean_currency(val) -> float:
    if pd.isna(val):
        return 0.0
    val_str = str(val).strip()
    
    # Handle accounting format: (123.45) -> -123.45
    is_negative = False
    if val_str.startswith('(') and val_str.endswith(')'):
        is_negative = True
        val_str = val_str[1:-1]
    elif val_str.startswith('-'):
        is_negative = True
        val_str = val_str[1:]
        
    # Remove currency symbols and commas
    val_str = re.sub(r'[^\d.]', '', val_str)
    
    if not val_str:
        return 0.0
        
    try:
        num = float(val_str)
        return -num if is_negative else num
    except ValueError:
        return 0.0

def validate_mappings(mappings: dict) -> str:
    """
    Validates the mapped columns.
    Returns an error message string if invalid, or None if valid.
    """
    if mappings is None:
        return "No mappings found."
        
    mapped_fields = list(mappings.values())
    
    has_date = "Date" in mapped_fields
    has_desc = "Description" in mapped_fields
    has_amount = "Amount" in mapped_fields
    has_deposit = "Deposit" in mapped_fields
    has_withdrawal = "Withdrawal" in mapped_fields
    
    if not has_date or not has_desc:
        return "Must map at least 'Date' and 'Description'."
        
    if has_amount and (has_deposit or has_withdrawal):
        return "Cannot map 'Amount' alongside 'Deposit' or 'Withdrawal'."
        
    if has_deposit and not has_withdrawal:
        return "Mapped 'Deposit' but missing 'Withdrawal'."
        
    if has_withdrawal and not has_deposit:
        return "Mapped 'Withdrawal' but missing 'Deposit'."
        
    if not has_amount and not (has_deposit and has_withdrawal):
        return "Must map either 'Amount', or both 'Deposit' and 'Withdrawal'."
        
    return None

def determine_mapping_type(mappings: dict) -> str:
    """Returns 'amount' or 'deposit_withdrawal' based on mappings."""
    if mappings is None:
        return None
    if "Amount" in mappings.values():
        return "amount"
    return "deposit_withdrawal"

def prepare_page_data(df: pd.DataFrame, mappings: dict, disabled_rows: set, page_num: int, default_year: int) -> tuple[pd.DataFrame, list]:
    """
    Filters disabled rows and unmapped columns.
    Returns a clean DataFrame with ['Date', 'Amount', 'Description'] and a list of error dictionaries.
    """
    errors = []
    
    # 1. Filter rows
    valid_rows = [i for i in range(len(df)) if i not in disabled_rows]
    clean_df = df.iloc[valid_rows].copy()
    
    # 2. Extract mapped columns
    inv_map = {v: k for k, v in mappings.items() if v != "Unmapped"}
    
    date_col = inv_map.get("Date")
    desc_col = inv_map.get("Description")
    
    result = pd.DataFrame()
    
    # Handle dates using mixed format so a single weird date doesn't ruin format inference for the rest
    dates = pd.to_datetime(clean_df[date_col], errors='coerce', format='mixed')
    
    def fix_year(dt):
        if pd.isna(dt):
            return dt
        if dt.year == 1 or dt.year == 1900:
            try:
                return dt.replace(year=default_year)
            except ValueError:
                # Handle leap year edge cases (e.g. Feb 29 on year 1 replacing into a non-leap year)
                return dt.replace(year=default_year, day=28)
        return dt
        
    dates = dates.apply(fix_year)
    
    for original_idx, val in dates.items():
        if pd.isna(val):
            # Log as error if date couldn't be parsed
            errors.append({'page': page_num, 'row': original_idx, 'col': date_col})
            
    result['Date'] = dates
    result['Description'] = clean_df[desc_col].astype(str)
    
    # Helper to clean currency and track errors
    def apply_currency(col_idx):
        vals = []
        for original_idx, val in clean_df[col_idx].items():
            if pd.isna(val):
                vals.append(0.0)
                continue
                
            v_str = str(val).strip()
            if not v_str:
                vals.append(0.0)
                continue
                
            is_neg = False
            if v_str.startswith('(') and v_str.endswith(')'):
                is_neg, v_str = True, v_str[1:-1]
            elif v_str.startswith('-'):
                is_neg, v_str = True, v_str[1:]
                
            cleaned = re.sub(r'[^\d.]', '', v_str)
            if not cleaned:
                errors.append({'page': page_num, 'row': original_idx, 'col': col_idx})
                vals.append(0.0)
                continue
                
            try:
                num = float(cleaned)
                vals.append(-num if is_neg else num)
            except ValueError:
                errors.append({'page': page_num, 'row': original_idx, 'col': col_idx})
                vals.append(0.0)
                
        return pd.Series(vals, index=clean_df.index)

    # Handle Amounts
    if "Amount" in inv_map:
        amt_col = inv_map["Amount"]
        result['Amount'] = apply_currency(amt_col)
    else:
        dep_col = inv_map["Deposit"]
        wit_col = inv_map["Withdrawal"]
        
        deposits = apply_currency(dep_col)
        withdrawals = apply_currency(wit_col)
        
        withdrawals = -withdrawals.abs()
        result['Amount'] = deposits + withdrawals
        
    # Drop rows with NaT dates
    result = result.dropna(subset=['Date'])
    
    return result, errors

def export_to_ofx(df: pd.DataFrame, file_path: str):
    """
    Generates OFX content and writes to file_path.
    df must have ['Date', 'Amount', 'Description']
    """
    ofx_header = (
        "OFXHEADER:100\n"
        "DATA:OFXSGML\n"
        "VERSION:102\n"
        "SECURITY:NONE\n"
        "ENCODING:USASCII\n"
        "CHARSET:1252\n"
        "COMPRESSION:NONE\n"
        "OLDFILEUID:NONE\n"
        "NEWFILEUID:NONE\n\n"
    )

    ofx_body = (
        "<OFX>\n"
        "  <BANKMSGSRSV1>\n"
        "    <STMTTRNRS>\n"
        "      <TRNUID>1</TRNUID>\n"
        "      <STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>\n"
        "      <STMTRS>\n"
        "        <CURDEF>USD</CURDEF>\n"
        "        <BANKACCTFROM>\n"
        "          <BANKID>123456789</BANKID>\n"
        "          <ACCTID>123456789</ACCTID>\n"
        "          <ACCTTYPE>CHECKING</ACCTTYPE>\n"
        "        </BANKACCTFROM>\n"
        "        <BANKTRANLIST>\n"
    )

    transactions = []
    # Use enumerate to guarantee a unique FITID
    for idx, (_, row) in enumerate(df.iterrows()):
        # Format Date as YYYYMMDDHHMMSS
        date_val = row['Date'].strftime('%Y%m%d000000')
        amount_val = f"{row['Amount']:.2f}"
        desc_val = str(row['Description']).strip()

        trn_type = "CREDIT" if row['Amount'] >= 0 else "DEBIT"

        txn = (
            "          <STMTTRN>\n"
            f"            <TRNTYPE>{trn_type}</TRNTYPE>\n"
            f"            <DTPOSTED>{date_val}</DTPOSTED>\n"
            f"            <TRNAMT>{amount_val}</TRNAMT>\n"
            f"            <FITID>{idx}</FITID>\n"
            f"            <NAME>{desc_val}</NAME>\n"
            "          </STMTTRN>\n"
        )
        transactions.append(txn)

    ofx_footer = (
        "        </BANKTRANLIST>\n"
        "      </STMTRS>\n"
        "    </STMTTRNRS>\n"
        "  </BANKMSGSRSV1>\n"
        "</OFX>\n"
    )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(ofx_header + ofx_body + "".join(transactions) + ofx_footer)
