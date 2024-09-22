import multiprocessing
import subprocess

# Function to run the first Python file
def run_channel_1():
    subprocess.run(['python', 'channel_1.py'])

# Function to run the second Python file
def run_channel_2():
    subprocess.run(['python', 'channel_2.py'])

if __name__ == "__main__":
    # Create two processes for the two Python files
    p1 = multiprocessing.Process(target=run_channel_1)
    p2 = multiprocessing.Process(target=run_channel_2)

    # Start both processes
    p1.start()
    p2.start()

    # Wait for both processes to complete
    p1.join()
    p2.join()

    print("Both scripts have finished execution.")
