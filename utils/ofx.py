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
    result['Description'] = clean_df[desc_col].astype(str).apply(lambda x: re.sub(r'\s+', ' ', x).strip())
    
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
    Format matches Servus Credit Union OFX output for Sage 50 Canada compatibility.
    """
    import hashlib
    import time

    now_str = pd.Timestamp.now().strftime('%Y%m%d%H%M%S') + '[-6:CST]'

    if df.empty:
        dtstart = '19700101000000[-6:CST]'
        dtend = '19700101000000[-6:CST]'
    else:
        dtstart = df['Date'].min().strftime('%Y%m%d') + '000000[-6:CST]'
        dtend = df['Date'].max().strftime('%Y%m%d') + '000000[-6:CST]'

    export_salt = str(time.time())

    lines = []
    # Header
    lines.append('OFXHEADER:100')
    lines.append('DATA:OFXSGML')
    lines.append('VERSION:102')
    lines.append('SECURITY:TYPE1')
    lines.append('ENCODING:USASCII')
    lines.append('CHARSET:1252')
    lines.append('COMPRESSION:NONE')
    lines.append('OLDFILEUID:NONE')
    lines.append('NEWFILEUID:NONE')
    lines.append('')
    # Body
    lines.append('<OFX>')
    lines.append(' <SIGNONMSGSRSV1>')
    lines.append('  <SONRS>')
    lines.append('   <STATUS>')
    lines.append('    <CODE>0')
    lines.append('    <SEVERITY>INFO')
    lines.append('    <MESSAGE>OK')
    lines.append('   </STATUS>')
    lines.append(f'   <DTSERVER>{now_str}')
    lines.append('   <LANGUAGE>ENG')
    lines.append('  </SONRS>')
    lines.append(' </SIGNONMSGSRSV1>')
    lines.append(' <BANKMSGSRSV1>')
    lines.append('  <STMTTRNRS>')
    lines.append('   <TRNUID>0000000000001')
    lines.append('   <STATUS>')
    lines.append('    <CODE>0')
    lines.append('    <SEVERITY>INFO')
    lines.append('    <MESSAGE>OK')
    lines.append('   </STATUS>')
    lines.append('   <STMTRS>')
    lines.append('    <CURDEF>CAD')
    lines.append('    <BANKACCTFROM>')
    lines.append('     <BANKID>0')
    lines.append('     <BRANCHID>000')
    lines.append('     <ACCTID>0')
    lines.append('     <ACCTTYPE>CHECKING')
    lines.append('    </BANKACCTFROM>')
    lines.append('    <BANKTRANLIST>')
    lines.append(f'     <DTSTART>{dtstart}')
    lines.append(f'     <DTEND>{dtend}')

    # Transactions
    for idx, (_, row) in enumerate(df.iterrows()):
        date_val = row['Date'].strftime('%Y%m%d') + '000000[-6:CST]'
        amount_val = f"{row['Amount']:.2f}"
        desc_val = re.sub(r'\s+', ' ', str(row['Description'])).strip()

        trn_type = "CREDIT" if row['Amount'] >= 0 else "DEBIT"

        raw_id = f"{date_val}{amount_val}{desc_val}{idx}{export_salt}"
        fitid = hashlib.md5(raw_id.encode('utf-8')).hexdigest()[:12]

        lines.append('     <STMTTRN>')
        lines.append(f'      <TRNTYPE>{trn_type}')
        lines.append(f'      <DTPOSTED>{date_val}')
        lines.append(f'      <TRNAMT>{amount_val}')
        lines.append(f'      <FITID>{fitid}')
        lines.append(f'      <NAME>{desc_val}')
        lines.append('     </STMTTRN>')

    # Footer
    lines.append('    </BANKTRANLIST>')
    lines.append('   </STMTRS>')
    lines.append('  </STMTTRNRS>')
    lines.append(' </BANKMSGSRSV1>')
    lines.append('</OFX>')
    lines.append('')

    with open(file_path, 'w', encoding='ascii', errors='replace', newline='\r\n') as f:
        f.write('\n'.join(lines))
