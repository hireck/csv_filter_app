import subprocess
import tempfile
import os
import shutil
import glob
from pathlib import Path

class SafeCodeExecutorWithInputs:
    def __init__(self, timeout=5, max_memory_mb=50, input_directory=None):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.temp_dir = None
        
        # Set default input directory to current working directory
        self.input_directory = input_directory or os.getcwd()
    
    def extract_code_blocks(self, text):
        """Extract code blocks from text using simple regex"""
        import re
        pattern = r'<code language="python">(.*?)</code>'
        matches = re.findall(pattern, text, re.DOTALL)
        if not matches:
            pattern = r'```python(.*?)```' #The LLM has a tendency to do this instead of html tags
            matches = re.findall(pattern, text, re.DOTALL)
        return [code.strip() for code in matches]
    
    def validate_code(self, code):
        """Basic validation - check if code is syntactically correct"""
        import ast
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
    
    def check_dangerous_imports(self, code):
        """Check for potentially dangerous imports/operations"""
        dangerous_patterns = [
            'import os',
            'import subprocess',
            'import sys',
            '__import__',
            'eval(',
            'exec(',
            'open(',
            'file(',
            'input(',
            'raw_input(',
        ]
        
        for pattern in dangerous_patterns:
            if pattern in code:
                return False, f"Dangerous operation detected: {pattern}"
        return True, None 
       
    # def setup_input_files(self, input_files=None):
    #     """Copy specified input files to the execution directory"""
    #     if not input_files:
    #         return []
            
    #     copied_files = []
        
    #     for file_path in input_files:
    #         # Handle both absolute and relative paths
    #         if not os.path.isabs(file_path):
    #             source_path = os.path.join(self.input_directory, file_path)
    #         else:
    #             source_path = file_path
                
    #         if os.path.exists(source_path):
    #             # Copy to execution directory with same name
    #             dest_path = os.path.join(self.temp_dir, os.path.basename(source_path))
    #             shutil.copy2(source_path, dest_path)
    #             copied_files.append(os.path.basename(source_path))
    #             print(f"📁 Copied input file: {os.path.basename(source_path)}")
    #         else:
    #             print(f"⚠️  Input file not found: {source_path}")
                
    #     return copied_files
    
    def setup_all_files_from_directory(self, directory_path=None):
        """Copy all files from a directory to the execution environment"""
        source_dir = directory_path or self.input_directory
        
        if not os.path.exists(source_dir):
            print(f"⚠️  Input directory not found: {source_dir}")
            return []
            
        copied_files = []
        
        # Copy all files (not directories) from source directory
        for item in os.listdir(source_dir):
            source_path = os.path.join(source_dir, item)
            
            if os.path.isfile(source_path):
                dest_path = os.path.join(self.temp_dir, item)
                shutil.copy2(source_path, dest_path)
                copied_files.append(item)
                
        print(f"📁 Copied {len(copied_files)} files from {source_dir}")
        return copied_files
    
    def execute_with_inputs(self, code, input_files=None, copy_all_inputs=False):
        """Execute code with access to specified input files"""
        # Create execution directory
        self.temp_dir = tempfile.mkdtemp(prefix="code_exec_")
        
        try:
            # Set up input files
            if copy_all_inputs:
                available_files = self.setup_all_files_from_directory()
            #else:
                #available_files = self.setup_input_files(input_files)
            
            # Show available files to the code
            if available_files:
                print(f"📂 Available input files: {', '.join(available_files)}")
            
            # Modify code to run in temp directory
            modified_code = f'''
import os
os.chdir(r"{self.temp_dir}")

# List available files for debugging
#import glob
#available_files = glob.glob("*")
#if available_files:
    #print("Available files in execution directory:", available_files)

# Original code
{code}
'''
            
            # Create and execute script
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(modified_code)
                temp_script = f.name
            
            try:
                cmd = [
                    'python3',
                    '-c',
                    f'''
import sys
import resource

# Set memory limit
#resource.setrlimit(resource.RLIMIT_AS, ({self.max_memory_mb * 1024 * 1024}, {self.max_memory_mb * 1024 * 1024}))

# Execute the script
with open("{temp_script}", "r") as f:
    code = f.read()
    exec(code)
'''
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                
                # Check for output files (CSV, etc.)
                temp_files = []
                for pattern in ["*.csv"]:#, "*.txt", "*.json", "*.xlsx"]:
                    temp_files.extend(glob.glob(os.path.join(self.temp_dir, pattern)))
                #print("output_files: ", output_files)
                output_files = []
                for f in temp_files:
                    filename = os.path.basename(f)
                    if ".to_csv('"+filename in code:
                        output_files.append(filename)


                return {
                    'success': result.returncode == 0,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'input_files': available_files,
                    'output_files': [os.path.basename(f) for f in output_files],
                    'temp_dir': self.temp_dir
                }
                
            except subprocess.TimeoutExpired:
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': f'Code execution timed out after {self.timeout} seconds',
                    'input_files': available_files,
                    'output_files': [],
                    'temp_dir': self.temp_dir
                }
            finally:
                try:
                    os.unlink(temp_script)
                except:
                    pass
                    
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': f'Setup error: {str(e)}',
                'input_files': [],
                'output_files': [],
                'temp_dir': self.temp_dir
            }
        
    def execute_safe(self, llm_response):
        """Main method to safely execute code from LLM response"""
        print('Extracting code')
        results = []
        
        # Extract code blocks
        code_blocks = self.extract_code_blocks(llm_response)
        for cb in code_blocks:
            print(cb)
        
        if not code_blocks:
            return []#{'error': 'No code blocks found in response'}
        
        for i, code in enumerate(code_blocks):
            print(f"\n--- Executing Code Block {i+1} ---")
            print(f"Code:\n{code}\n")
            
            # Validate syntax
            is_valid, error = self.validate_code(code)
            if not is_valid:
                result = {
                    'block_index': i,
                    'success': False,
                    'error': error,
                    'stdout': '',
                    'stderr': error
                }
                results.append(result)
                continue
            
            # Check for dangerous operations
            is_safe, error = self.check_dangerous_imports(code)
            if not is_safe:
                result = {
                    'block_index': i,
                    'success': False,
                    'error': error,
                    'stdout': '',
                    'stderr': error
                }
                results.append(result)
                continue
            execution_result = self.execute_with_inputs(code, copy_all_inputs=True)
            execution_result['block_index'] = i
            results.append(execution_result)
            
            # Print results
            if execution_result['success']:
                print(f"✅ Success!")
                if execution_result['stdout']:
                    print(f"Output: {execution_result['stdout']}")
                    print(f"Output files: {execution_result['output_files']}")
                    # for fn in execution_result['output_files']:
                    #     if not fn in execution_result['input_files']:
                    #         source_path = os.path.join(self.temp_dir, fn)
                    #         dest_path = os.path.join(self.input_directory, fn)
                    #         shutil.copy2(source_path, dest_path)
            else:
                print(f"❌ Failed!")
                if execution_result['stderr']:
                    print(f"Error: {execution_result['stderr']}")
        
        return results
            
    def cleanup(self):
        """Clean up temporary directory"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"🧹 Cleaned up temp directory")
            except:
                print(f"⚠️  Could not clean up temp directory")


# Example usage
if __name__ == "__main__":
    # Create some sample input files for testing
    os.makedirs("input_data", exist_ok=True)
    
    # Create sample CSV input
    with open("input_data/sample_input.csv", "w") as f:
        f.write("name,age,salary\n")
        f.write("Alice,25,50000\n")
        f.write("Bob,30,60000\n")
        f.write("Charlie,35,70000\n")
    
    # Create sample text input
    with open("input_data/config.txt", "w") as f:
        f.write("processing_mode=advanced\n")
        f.write("output_format=csv\n")
        f.write("max_records=1000\n")
    
    print("Created sample input files in 'input_data/' directory")
    print("=" * 60)
    
    # Sample code that processes input files
    processing_code = '''
import csv
import pandas as pd

# Read the CSV input file
print("Reading input CSV file...")
with open('sample_input.csv', 'r') as f:
    reader = csv.DictReader(f)
    data = list(reader)
    
print(f"Loaded {len(data)} records from input file")

# Read configuration
print("Reading configuration...")
config = {}
with open('config.txt', 'r') as f:
    for line in f:
        if '=' in line:
            key, value = line.strip().split('=', 1)
            config[key] = value

print(f"Configuration: {config}")

# Process the data
print("Processing data...")
output_data = []
for row in data:
    processed_row = {
        'name': row['name'],
        'age': int(row['age']),
        'salary': int(row['salary']),
        'salary_category': 'High' if int(row['salary']) > 55000 else 'Low'
    }
    output_data.append(processed_row)

# Write processed output
print("Writing output file...")
with open('processed_output.csv', 'w', newline='') as f:
    if output_data:
        writer = csv.DictWriter(f, fieldnames=output_data[0].keys())
        writer.writeheader()
        writer.writerows(output_data)

print("Processing complete! Output saved to 'processed_output.csv'")
'''
    
    # Method 1: Specify specific input files
    print("\\n🔧 Method 1: Specifying specific input files")
    print("-" * 40)
    
    executor1 = SafeCodeExecutorWithInputs(
        timeout=10, 
        input_directory="input_data"
    )
    
    result1 = executor1.execute_with_inputs(
        processing_code,
        input_files=["sample_input.csv", "config.txt"]
    )
    
    print(f"Success: {result1['success']}")
    print(f"Input files: {result1['input_files']}")
    print(f"Output files: {result1['output_files']}")
    if result1['stdout']:
        print(f"Output:\\n{result1['stdout']}")
    
    # Method 2: Copy all files from input directory
    print("\\n🔧 Method 2: Copy all files from input directory")
    print("-" * 40)
    
    executor2 = SafeCodeExecutorWithInputs(
        timeout=10,
        input_directory="input_data"
    )
    
    result2 = executor2.execute_with_inputs(
        processing_code,
        copy_all_inputs=True
    )
    
    print(f"Success: {result2['success']}")
    print(f"Input files: {result2['input_files']}")
    print(f"Output files: {result2['output_files']}")
    
    # Cleanup
    executor1.cleanup()
    executor2.cleanup()