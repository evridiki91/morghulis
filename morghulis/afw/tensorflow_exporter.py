# -*- coding: utf-8 -*-
import hashlib
import io
import logging
import os

import tensorflow as tf
from PIL import Image as PilImage

from morghulis.os_utils import ensure_dir

log = logging.getLogger(__name__)


def int64_feature(value):
    return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))


def int64_list_feature(value):
    return tf.train.Feature(int64_list=tf.train.Int64List(value=value))


def bytes_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))


def bytes_list_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=value))


def float_list_feature(value):
    return tf.train.Feature(float_list=tf.train.FloatList(value=value))


class TensorflowExporter:

    def __init__(self, ds):
        self.dataset = ds

    def _is_valid(self, face):
        if face.invalid or face.w <= 0.0 or face.h <= 0.0:
            return False
        return True

    def _convert(self, image):
        with tf.gfile.GFile(image.filename, 'rb') as fid:
            encoded_jpg = fid.read()
        encoded_jpg_io = io.BytesIO(encoded_jpg)
        img_data = PilImage.open(encoded_jpg_io)

        if img_data.format != 'JPEG':
            raise ValueError('Image format not JPEG')

        key = hashlib.sha256(encoded_jpg).hexdigest()
        width = img_data.width
        height = img_data.height
        xmins = []
        ymins = []
        xmaxs = []
        ymaxs = []
        classes = []
        classes_text = []
        truncated = []
        poses = []
        difficult_obj = []

        for face in image.faces:

            if not self._is_valid(face):
                continue

            xmin = max(0.005, (face.x1 / width))
            ymin = max(0.005, (face.y1 / height))
            xmax = min(0.995, (face.x2 / width))
            ymax = min(0.995, (face.y2 / height))

            if ymin > ymax or xmin > xmax:
                log.error('Invalid face dimensions %s in %s of %s', (xmin, ymin, xmax, ymax), face, image)
                continue

            xmins.append(xmin)
            ymins.append(ymin)
            xmaxs.append(xmax)
            ymaxs.append(ymax)

            classes_text.append('face')
            classes.append(1)
            poses.append("unspecified".encode('utf8'))
            # truncated.append(int(1) if face.occlusion > 0 else int(0))
            difficult_obj.append(int(0))

        _, filename = os.path.split(image.filename)

        feature_dict = {
            'image/height': int64_feature(height),
            'image/width': int64_feature(width),
            'image/filename': bytes_feature(filename.encode('utf8')),
            'image/source_id': bytes_feature(filename.encode('utf8')),
            'image/key/sha256': bytes_feature(key.encode('utf8')),
            'image/encoded': bytes_feature(encoded_jpg),
            'image/format': bytes_feature('jpeg'.encode('utf8')),
            'image/object/bbox/xmin': float_list_feature(xmins),
            'image/object/bbox/xmax': float_list_feature(xmaxs),
            'image/object/bbox/ymin': float_list_feature(ymins),
            'image/object/bbox/ymax': float_list_feature(ymaxs),
            'image/object/class/text': bytes_list_feature(classes_text),
            'image/object/class/label': int64_list_feature(classes),
            'image/object/difficult': int64_list_feature(difficult_obj),
            'image/object/truncated': int64_list_feature(truncated),
            'image/object/view': bytes_list_feature(poses),
        }
        example = tf.train.Example(features=tf.train.Features(feature=feature_dict))
        return example

    def _export(self, target_dir, dataset_name='train'):
        log.info('Converting %s data', dataset_name)
        output_filename = os.path.join(target_dir, 'afw_{}.record'.format(dataset_name))
        log.info('Loading {} set, it might take a while'.format(dataset_name))
        examples = [ex for ex in self.dataset.images()]
        log.info('Generating tf_record for %s set: %s example(s)', dataset_name, len(examples))
        self._generate_tf_records(output_filename, examples)

    def _generate_tf_records(self, output_filename, examples):
        writer = tf.python_io.TFRecordWriter(output_filename)
        for idx, example in enumerate(examples):
            if idx % 100 == 0:
                logging.info('On image %d of %d', idx, len(examples))
            try:
                tf_example = self._convert(example)
                writer.write(tf_example.SerializeToString())
            except Exception:
                logging.warning('Invalid example: %s, ignoring.', example)
        writer.close()

    def export(self, output_dir):
        ensure_dir(output_dir)
        self._export(output_dir, 'train')
