import random
import time


def generate_stream(letters, num_stimuli, letter_offset=10, letter_distances=(1,2,3,4,5)):
    stream = [random.randint(0,9) for _ in range(num_stimuli)]
    pos = letter_offset + random.randint(0, len(stream)-max(letter_distances)-letter_offset-1)
    letters = [random.choice(letters) for _ in range(2)]
    stream[pos] = letters[0]
    stream[pos + random.choice(letter_distances)] = letters[1]
    return stream


def attentional_blink_experiment():
    stream_duration = 4  # Duration of the entire stream in seconds
    stimulus_duration = 0.1  # Duration of each stimulus in seconds
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    letters = "ACHJKLMNPQRTVWXYZ"

    stream = generate_stream(letters, int(stream_duration / stimulus_duration))
    
    print("Attentional Blink Experiment")
    print("Detect the letters in the stream.")

    for i, stimulus in enumerate(stream):
        print(f'{stimulus}{stimulus}{stimulus}{stimulus}', end="\r", flush=True)
        time.sleep(stimulus_duration)

    print(f"\n{stream}")


if __name__ == "__main__":
    attentional_blink_experiment()
