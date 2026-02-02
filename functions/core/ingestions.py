import pandas as pd
import re

def clean_csv_to_psv_pandas(input_file, output_file):
    """
    Clean CSV file and convert to PSV format using pandas.
    
    Args:
        input_file (str): Path to input CSV file
        output_file (str): Path to output PSV file
    """
    # Read CSV with proper handling of quoted multi-line fields
    df = pd.read_csv(
        input_file,
        quoting=1,  # QUOTE_ALL
        escapechar='\\',
        on_bad_lines='skip'  # Skip malformed lines
    )
    
    # Clean ISCED_LEVELS_NAME - remove brackets, quotes, newlines, backslashes
    if 'ISCED_LEVELS_NAME' in df.columns:
        df['ISCED_LEVELS_NAME'] = df['ISCED_LEVELS_NAME'].apply(
            lambda x: re.sub(r'[\[\]"\\n\r]', '', str(x)).strip() if pd.notna(x) else ''
        )
    
    # Clean all fields - fix escaped commas and [None] values
    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: str(x).replace('\\,', ',').replace('\\', '').replace('\n', ' ').replace('\r', ' ').strip() 
            if pd.notna(x) else ''
        )
        df[col] = df[col].replace('[None]', '')
        df[col] = df[col].replace('nan', '')
        df[col] = df[col].replace('NaN', '')
    
    # Write as PSV
    df.to_csv(output_file, sep='|', index=False, quoting=0)  # QUOTE_NONE for output
    
    print(f"✅ Cleaned and converted {input_file} to {output_file}")
    print(f"   Total rows: {len(df)}")
    return df