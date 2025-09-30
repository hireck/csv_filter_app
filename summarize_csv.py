import pandas as pd
import numpy as np
from collections import Counter
import os

def summarize_csv(file_path, data_dir, max_unique_values=20, sample_size=5):
    """
    Reads a CSV file and provides a comprehensive summary of its structure and content.
    
    Parameters:
    file_path (str): Path to the CSV file
    max_unique_values (int): Maximum number of unique values to display for categorical columns
    sample_size (int): Number of example values to show for non-categorical columns
    """
    
    try:
        # Read the CSV file
        df = pd.read_csv(file_path)
        info = []
        print(f"CSV File Summary: {file_path}")
        print("=" * 50)
        print(f"Total rows: {len(df)}")
        print(f"Total columns (original file): {len(df.columns)}")
        print()
        info.append(f"CSV File Summary: {file_path}")
        info.append("=" * 50)
        info.append(f"Total rows: {len(df)}")
        info.append(f"Total columns (original file): {len(df.columns)}")
        info.append('')
        
        # Analyze each column
        column_info = []
        no_values = []
        one_value = []
        informative_columns = []
        #for i, column in enumerate(df.columns, 1):
        for column in df.columns:
            #print(f"{i}. Column: '{column}'")
            #print(f"   Data type: {df[column].dtype}")
            
            
            # Get unique values
            unique_values = df[column].dropna().unique()
            unique_count = len(unique_values)
            #print(f"   Unique values: {unique_count}")

            if unique_count == 0:
                no_values.append(column)
            elif unique_count == 1:
                one_value.append((column, unique_values.tolist()[0]))
            else:
                informative_columns.append(column)
                print(f"Column: '{column}'")
                print(f"   Unique values: {unique_count}")
                column_info.append(f"Column: '{column}'")
                column_info.append(f"   Unique values: {unique_count}")
                # Count non-null values
                non_null_count = df[column].count()
                null_count = len(df) - non_null_count
                #print(f"   Non-null values: {non_null_count}")
                if null_count > 0:
                    print(f"   Null values: {null_count}")
                    column_info.append(f"   Null values: {null_count}")
                
                # Determine if it's categorical or continuous
                if unique_count <= max_unique_values and unique_count > 0:
                    # Limited set of values - show all
                    print(f"   All values: {sorted(unique_values.tolist())}")
                    column_info.append(f"   All values: {sorted(unique_values.tolist())}")
                else:
                    # Many values - show examples and statistics
                    if df[column].dtype in ['int64', 'float64']:
                        # Numeric column
                        print(f"   Min: {df[column].min()}")
                        print(f"   Max: {df[column].max()}")
                        print(f"   Mean: {df[column].mean():.2f}")
                        print(f"   Examples: {df[column].dropna().head(sample_size).tolist()}")
                        column_info.append(f"   Min: {df[column].min()}")
                        column_info.append(f"   Max: {df[column].max()}")
                        column_info.append(f"   Mean: {df[column].mean():.2f}")
                        column_info.append(f"   Examples: {df[column].dropna().head(sample_size).tolist()}")
                    else:
                        # Text/object column
                        print(f"   Examples: {df[column].dropna().head(sample_size).tolist()}")
                        column_info.append(f"   Examples: {df[column].dropna().head(sample_size).tolist()}")
                        
                        # Show most common values if it's categorical-like
                        if unique_count < len(df) * 0.8:  # If less than 80% are unique
                            most_common = Counter(df[column].dropna()).most_common(5)
                            print(f"   Most common: {most_common}")
                            column_info.append(f"   Most common: {most_common}")
                
                print()
                column_info.append('')
        

        extra_info = []
        # Additional summary statistics
        #print("Additional Information:")
        print("-" * 30)
        print("Columns without data: ", no_values)
        if no_values:
            extra_info.append("Columns without data: " + ', '.join(no_values))
        print()
        if one_value:
            extra_info.append("Columns where all rows have the same value: " + ', '.join([c+' ('+str(v)+')' for c, v in one_value]))
        for c, v in one_value:
            print(c+": "+str(v))
        
        # Memory usage
        #memory_usage = df.memory_usage(deep=True).sum()
        #print(f"Memory usage: {memory_usage / 1024:.2f} KB")
        
        # Duplicate rows
        duplicate_count = df.duplicated().sum()
        if duplicate_count > 0:
            print(f"Duplicate rows: {duplicate_count}")
            info.append(f"Duplicate rows: {duplicate_count}")
        
        # Columns with missing data
        #columns_with_nulls = df.columns[df.isnull().any()].tolist()
        #if columns_with_nulls:
            #print(f"Columns with missing data: {columns_with_nulls}")

        # Create filtered dataframe
        df_filtered = df[informative_columns].copy()
        info.append(f"Total columns (informative): {len(df_filtered.columns)}")
        info.append('')
        
        # Generate output filename if not provided
        
        output_file = os.path.basename(file_path).replace('.csv', '_informative.csv')
        output_file = output_file.replace(' ', '_')
        output_path = os.path.join(data_dir, output_file)
           
        
        # Save filtered dataframe
        df_filtered.to_csv(output_path, index=False)
        print(f"\nFiltered dataset saved as: {output_file}")
        print(f"New dataset: {len(df_filtered)} rows, {len(df_filtered.columns)} columns")

        return info, column_info, extra_info, output_file
    
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
    except pd.errors.EmptyDataError:
        print(f"Error: File '{file_path}' is empty.")
    except Exception as e:
        print(f"Error reading file: {str(e)}")

# Example usage
if __name__ == "__main__":
    # Replace 'your_file.csv' with the actual path to your CSV file
    csv_file_path = "data sample.csv"
    info, column_info, extra_info, output_file = summarize_csv(csv_file_path)
    print(output_file)
    print('\n'.join(info))
    print('\n'.join(column_info))
    print('\n'.join(extra_info))
    
    # You can also customize the parameters:
    # summarize_csv("your_file.csv", max_unique_values=10, sample_size=3)