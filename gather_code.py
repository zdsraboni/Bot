import os

# যে ফোল্ডারগুলো আমরা স্কিপ করব
IGNORE_FOLDERS = {'venv', '.git', '__pycache__', '.idea', '.vscode', 'env'}
# যে এক্সটেনশনের ফাইলগুলো আমরা নেব
INCLUDE_EXTS = {'.py', '.json', '.txt', '.md', '.html', '.css', '.js'}

def merge_project_files(output_file='full_project_code.txt'):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        # বর্তমান ডিরেক্টরি থেকে খোঁজা শুরু
        for root, dirs, files in os.walk('.'):
            # ইগনোর করা ফোল্ডারগুলো লিস্ট থেকে সরিয়ে ফেলা হচ্ছে
            dirs[:] = [d for d in dirs if d not in IGNORE_FOLDERS]
            
            for file in files:
                ext = os.path.splitext(file)[1]
                # স্ক্রিপ্টটি নিজেকে কপি করবে না এবং শুধু নির্দিষ্ট এক্সটেনশন নেবে
                if ext in INCLUDE_EXTS and file != 'gather_code.py':
                    file_path = os.path.join(root, file)
                    try:
                        outfile.write(f"\n{'='*50}\n")
                        outfile.write(f"FILE START: {file_path}\n")
                        outfile.write(f"{'='*50}\n\n")
                        
                        with open(file_path, 'r', encoding='utf-8') as infile:
                            outfile.write(infile.read())
                            
                        outfile.write(f"\n\n{'='*50}\n")
                        outfile.write(f"FILE END: {file_path}\n")
                        outfile.write(f"{'='*50}\n")
                    except Exception as e:
                        print(f"Skipping file {file_path} due to error: {e}")

if __name__ == "__main__":
    merge_project_files()
    print("সফল হয়েছে! 'project_code.txt' ফাইলটি এখন আপলোড করুন।")
