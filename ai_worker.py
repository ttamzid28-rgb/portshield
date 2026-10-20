"""Private subprocess entry point. Secrets arrive over stdin, never command-line arguments."""
import json
import sys
from ai_runtime import execute_job

def main():
    request = json.load(sys.stdin)
    def progress(diagnostic):
        print(json.dumps({'event': 'progress', 'diagnostic': diagnostic}), flush=True)
    result = execute_job(request['job'], request['diagnostic'], progress)
    print(json.dumps({'event': 'result', 'result': result}), flush=True)

if __name__ == '__main__':
    main()
