from itertools import chain, filterfalse
from numbers import Integral
from typing import Iterable, Optional, Mapping, Text

import numpy as np

from src.structures import NetInput, Interval, Seq


def predict_and_dump(inp: NetInput, model, hparams: Mapping, cli_params, **kwargs):
    def prepare_seq(seq: Seq, pos: Iterable[int]) -> Optional[Text]:
        if not pos:
            return None
        seq_mut = list(seq.data.raw)
        for p in pos:
            seq_mut[p] = seq_mut[p].lower()
        return '\n'.join(map(lambda x: ''.join(x), (seq_mut[i:i + 80] for i in range(0, len(seq_mut), 80))))

    def prepare(to_dump):
        if cli_params['prediction_output_mode'] == 'tsv':
            return chain.from_iterable(("\t".join([id_, str(n + 1)]) for n in pos) for id_, _, pos in to_dump)
        seqs = filterfalse(lambda x: x is None, ((id_, prepare_seq(seq, pos)) for id_, seq, pos in to_dump))
        return ('\n'.join(('>' + id_, seq)) for id_, seq in seqs)

    ts = cli_params['threshold'] if cli_params['threshold'] is not None else hparams['threshold']
    bs = cli_params['batch_size'] if cli_params['batch_size'] is not None else hparams['batch_size']
    predictions = predict(model, inp, hparams['window_size'], batch_size=bs)
    valid_predictions = zip(inp.ids, inp.seqs, (np.where(p >= ts)[0] for p in predictions))
    prepared = filterfalse(lambda x: x is None, prepare(valid_predictions))
    for line in prepared:
        print(line, file=cli_params['output_file'])


def predict(model, inp: NetInput, window_size: Integral, batch_size: Integral = 100) \
        -> Iterable[np.ndarray]:
    """
    Predicts classes in merged array of sequences provided in inp
    Merges windowed predictions using intervals created by rolling_window function
    :param model: compiled keras model.
    :param window_size: size of a window
    :param inp: input to model.
    Must contain:
        1) joined (sequences)
        2) masks (False-padded rolled sequences)
        3) negative (ones for any potentially positive class)
        4) rolled sequences intervals
    :param batch_size:
    :return:
    """
    predictions = model.predict(
        [inp.joined, inp.masks[:, :, None], inp.negative[:, :, None]],
        batch_size=batch_size)
    split_intervals = (len(int_) * window_size for int_ in inp.rolled_seqs)
    predictions = np.split(predictions, np.array(list(split_intervals)[1:]))
    predictions = (_merge(a, ints) for a, ints in zip(predictions, inp.rolled_seqs))
    return predictions


def _merge(array: np.ndarray, intervals: Iterable[Interval], num_classes: Optional[Integral] = None) \
        -> np.ndarray:
    # TODO: docs
    """

    :param array:
    :param intervals:
    :param num_classes:
    :return:
    """
    denom = (np.zeros(shape=(max(int_.stop for int_ in intervals), num_classes)) if num_classes
             else np.zeros(shape=(max(int_.stop for int_ in intervals),)))
    merged = (np.zeros(shape=(max(int_.stop for int_ in intervals), num_classes)) if num_classes
              else np.zeros(shape=(max(int_.stop for int_ in intervals),)))
    for int_, arr in zip(intervals, array.reshape(array.shape[:-1])):
        merged[int_.start:int_.stop] += arr[:int_.stop - int_.start]
        denom[int_.start:int_.stop] += 1
    return merged / denom


if __name__ == '__main__':
    raise RuntimeError
