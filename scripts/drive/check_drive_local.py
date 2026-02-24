import os

def check_drive():
    path = r"G:\Mi unidad\Transcripts_Barca\SRT_YouTube"
    if os.path.exists(path):
        print(f"PATH_EXISTS: {path}")
        files = os.listdir(path)
        print(f"FILE_COUNT: {len(files)}")
        if files:
            print(f"SAMPLE_FILE: {files[0]}")
    else:
        print("PATH_NOT_FOUND")

if __name__ == "__main__":
    check_drive()
