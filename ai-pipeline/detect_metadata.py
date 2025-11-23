import argparse
import json
import sys
import os

# Add the current directory to sys.path to allow importing pipeline modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pipeline.metadata_detection import detect_song_metadata

def main():
    parser = argparse.ArgumentParser(description="Detect metadata for an audio file.")
    parser.add_argument("input_path", help="Path to the audio file")
    args = parser.parse_args()

    try:
        metadata = detect_song_metadata(args.input_path)
        print(json.dumps(metadata))
    except Exception as e:
        # Print error to stderr so it doesn't corrupt stdout JSON
        print(f"Error: {e}", file=sys.stderr)
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
