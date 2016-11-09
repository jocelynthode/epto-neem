#!/usr/bin/env python3.5
import re
from collections import namedtuple
import statistics
import argparse

Stats = namedtuple('Stats', ['start_at', 'end_at', 'duration', 'msg_sent', 'msg_received',
                             'balls_sent', 'balls_received'])

parser = argparse.ArgumentParser(description='Process EpTO logs')
parser.add_argument('files', metavar='FILE', nargs='+', type=str,
                    help='the files to parse')
parser.add_argument('-c', '--constant', metavar='CONSTANT', type=int, default=2,
                    help='the constant to find the minimum ratio we must have')
parser.add_argument('-e', '--experiments-nb',  metavar='EXPERIMENT_NB', type=int, default=1,
                    help='How many experiments were run')
args = parser.parse_args()
experiments_nb = args.experiments_nb
PEER_NUMBER = len(args.files) // experiments_nb

expected_ratio = 1 - (1 / (PEER_NUMBER**args.constant))
k = ttl = delta = 0


# We must create our own iter because iter disables the tell function
def textiter(file):
    line = file.readline()
    while line:
        yield line
        line = file.readline()


def extract_stats(file):
    global k, ttl, delta
    it = textiter(file)  # Force re-use of same iterator

    for line in it:
        match = re.match(r'\d+ - TTL: (\d+), K: (\d+)', line)
        if match:
            ttl = int(match.group(1))
            k = int(match.group(2))
            break

    def match_line(regexp_str):
        result = 0
        for line in it:
            match = re.match(regexp_str, line)
            if match:
                result = int(match.group(1))
                break
        return result

    delta = match_line(r'\d+ - Delta: (\d+)')
    start_at = match_line(r'(\d+) - Sending:')

    # We want the last occurrence in the file
    def find_end():
        result = None
        pos = None
        for line in it:
            match = re.match(r'(\d+) - Delivered', line)
            if match:
                result = int(match.group(1))
                pos = file.tell()

        file.seek(pos)
        return textiter(file), result

    it, end_at = find_end()
    balls_sent = match_line(r'\d+ - Balls sent: (\d+)')
    balls_received = match_line(r'\d+ - Balls received: (\d+)')
    messages_sent = match_line(r'\d+ - Events sent: (\d+)')
    messages_received = match_line(r'\d+ - Events received: (\d+)')

    return Stats(start_at, end_at, end_at - start_at, messages_sent,
                 messages_received, balls_sent, balls_received)


def all_stats():
    for file in args.files:
        with open(file, 'r') as f:
            file_stats = extract_stats(f)
        yield file_stats


def global_time(experiment_nb, stats):
    for i in range(experiment_nb):
        start_index = i * PEER_NUMBER
        end_index = start_index + PEER_NUMBER
        tmp = stats[start_index:end_index]
        mininum_start = min([stat.start_at for stat in tmp])
        maximum_end = max([stat.end_at for stat in tmp])
        yield(maximum_end - mininum_start)


stats = list(all_stats())
global_times = list(global_time(experiments_nb, stats))
durations = [stat.duration for stat in stats]
mininum = min(durations)
maximum = max(durations)
average = statistics.mean(durations)
global_average = statistics.mean(global_times)

print("EpTO run with %d peers across %d experiments" % (PEER_NUMBER, experiments_nb))
print("K=%d / TTL=%d / Delta=%dms" % (k, ttl, delta))
print("-------------------------------------------")
print("Least time to deliver in total : %d ms" % mininum)
print("Most time to deliver in total : %d ms" % maximum)
print("Average time to deliver per peer in total: %d ms" % average)
print("Average global time to deliver on all peers per experiment: %d ms" % global_average)
print("-------------------------------------------")
messages_sent = [stat.msg_sent for stat in stats]
messages_received = [stat.msg_received for stat in stats]
balls_sent = [stat.balls_sent for stat in stats]
balls_received = [stat.balls_received for stat in stats]

sent_sum = sum(messages_sent)
received_sum = sum(messages_received)
ratios = [(msg_received / sent_sum) for msg_received in messages_received]
print("Best ratio events received/sent: %.10g" % max(ratios))
print("Worst ratio events received/sent: %.10g" % min(ratios))
print("Total ratio events received/sent on average per peer : %.10g" % (statistics.mean(ratios)))
print("-------------------------------------------")
if min(ratios) >= expected_ratio:
    print("All ratios across all experiments satisfy the expected ratio of %.10g" % expected_ratio)
else:
    not_satisfying = 0
    for ratio in ratios:
        if ratio < expected_ratio:
            not_satisfying += 1
    print("%d peers across all experiments didn't satisfy the expected ratio of %.10g"
          % (not_satisfying, expected_ratio))
print("-------------------------------------------")
balls_sent_sum = sum(balls_sent)
balls_received_sum = sum(balls_received)
print("Total balls sent across all peers: %d" % balls_sent_sum)
print("Total balls received across all peers: %d" % balls_received_sum)
print("Total ratio balls received/sent: %f" % (balls_received_sum / balls_sent_sum))
print("-------------------------------------------")
for i in range(experiments_nb):
    start_index = i * PEER_NUMBER
    end_index = start_index + PEER_NUMBER
    print("Experiment %d:" % (i+1))
    print("Total events sent: %d" % (sum(messages_sent[start_index:end_index])))
    print("Total events received on average: %f"
          % (sum(messages_received[start_index:end_index]) / PEER_NUMBER))
    print("--------")

