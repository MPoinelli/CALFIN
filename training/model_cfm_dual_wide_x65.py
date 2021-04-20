# -*- coding: utf-8 -*-

""" Deeplabv3+ model for Keras.
This model is based on TF repo:
https://github.com/tensorflow/models/tree/master/research/deeplab
On Pascal VOC, original model gets to 84.56% mIOU

Now this model is only available for the TensorFlow backend,
due to its reliance on `SeparableConvolution` layers, but Theano will add
this layer soon.

MobileNetv2 backbone is based on this repo:
https://github.com/JonathanCMitchell/mobilenet_v2_keras

# Reference
- [Encoder-Decoder with Atrous Separable Convolution
    for Semantic Image Segmentation](https://arxiv.org/pdf/1802.02611.pdf)
- [Xception: Deep Learning with Depthwise Separable Convolutions]
    (https://arxiv.org/abs/1610.02357)
- [Inverted Residuals and Linear Bottlenecks: Mobile Networks for
    Classification, Detection and Segmentation](https://arxiv.org/abs/1801.04381)
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np

import tensorflow as tf
from tensorflow import keras

from keras.models import Model
from keras import layers
from keras.layers import Input
from keras.layers import Activation
from keras.layers import Concatenate
from keras.layers import Add
from keras.layers import Dropout
from keras.layers import BatchNormalization
from keras.layers import Conv2D
from keras.layers import DepthwiseConv2D
from keras.layers import ZeroPadding2D
from keras.layers import MaxPooling2D
from keras.layers import UpSampling2D
from keras.engine import Layer
from keras.engine import InputSpec
from keras.engine.topology import get_source_inputs
from keras import backend as K
from keras.applications import imagenet_utils
from keras.regularizers import l1, l2, l1_l2
from keras.utils import conv_utils
from keras.utils.data_utils import get_file
#from tensorflow.python.framework import tensor_shape

WEIGHTS_PATH_X = "https://github.com/bonlime/keras-deeplab-v3-plus/releases/download/1.1/deeplabv3_xception_tf_dim_ordering_tf_kernels.h5"
WEIGHTS_PATH_MOBILE = "https://github.com/bonlime/keras-deeplab-v3-plus/releases/download/1.1/deeplabv3_mobilenetv2_tf_dim_ordering_tf_kernels.h5"
WEIGHTS_PATH_X_CS = "https://github.com/rdiazgar/keras-deeplab-v3-plus/releases/download/1.2/deeplabv3_xception_tf_dim_ordering_tf_kernels_cityscapes.h5"
WEIGHTS_PATH_MOBILE_CS = "https://github.com/rdiazgar/keras-deeplab-v3-plus/releases/download/1.2/deeplabv3_mobilenetv2_tf_dim_ordering_tf_kernels_cityscapes.h5"
#class UpSampling2D(Layer):
#    """Upsampling layer for 2D inputs.
#    Repeats the rows and columns of the data
#    by `size[0]` and `size[1]` respectively.
#    Examples:
#    >>> input_shape = (2, 2, 1, 3)
#    >>> x = np.arange(np.prod(input_shape)).reshape(input_shape)
#    >>> print(x)
#    [[[[ 0    1    2]]
#        [[ 3    4    5]]]
#     [[[ 6    7    8]]
#        [[ 9 10 11]]]]
#    >>> y = tf.keras.layers.UpSampling2D(size=(1, 2))(x)
#    >>> print(y)
#    tf.Tensor(
#        [[[[ 0    1    2]
#             [ 0    1    2]]
#            [[ 3    4    5]
#             [ 3    4    5]]]
#         [[[ 6    7    8]
#             [ 6    7    8]]
#            [[ 9 10 11]
#             [ 9 10 11]]]], shape=(2, 2, 2, 3), dtype=int64)
#    Arguments:
#        size: Int, or tuple of 2 integers.
#            The upsampling factors for rows and columns.
#        data_format: A string,
#            one of `channels_last` (default) or `channels_first`.
#            The ordering of the dimensions in the inputs.
#            `channels_last` corresponds to inputs with shape
#            `(batch_size, height, width, channels)` while `channels_first`
#            corresponds to inputs with shape
#            `(batch_size, channels, height, width)`.
#            It defaults to the `image_data_format` value found in your
#            Keras config file at `~/.keras/keras.json`.
#            If you never set it, then it will be "channels_last".
#        interpolation: A string, one of `nearest` or `bilinear`.
#    Input shape:
#        4D tensor with shape:
#        - If `data_format` is `"channels_last"`:
#                `(batch_size, rows, cols, channels)`
#        - If `data_format` is `"channels_first"`:
#                `(batch_size, channels, rows, cols)`
#    Output shape:
#        4D tensor with shape:
#        - If `data_format` is `"channels_last"`:
#                `(batch_size, upsampled_rows, upsampled_cols, channels)`
#        - If `data_format` is `"channels_first"`:
#                `(batch_size, channels, upsampled_rows, upsampled_cols)`
#    """
#
#    def __init__(self,
#                             size=(2, 2),
#                             data_format=None,
#                             interpolation='nearest',
#                             **kwargs):
#        super(UpSampling2D, self).__init__(**kwargs)
#        self.data_format = conv_utils.normalize_data_format(data_format)
#        self.size = conv_utils.normalize_tuple(size, 2, 'size')
#        if interpolation not in {'nearest', 'bilinear'}:
#            raise ValueError('`interpolation` argument should be one of `"nearest"` '
#                                             'or `"bilinear"`.')
#        self.interpolation = interpolation
#        self.input_spec = InputSpec(ndim=4)
#
#    def compute_output_shape(self, input_shape):
#        input_shape = tensor_shape.TensorShape(input_shape).as_list()
#        if self.data_format == 'channels_first':
#            height = self.size[0] * input_shape[
#                    2] if input_shape[2] is not None else None
#            width = self.size[1] * input_shape[
#                    3] if input_shape[3] is not None else None
#            return tensor_shape.TensorShape(
#                    [input_shape[0], input_shape[1], height, width])
#        else:
#            height = self.size[0] * input_shape[
#                    1] if input_shape[1] is not None else None
#            width = self.size[1] * input_shape[
#                    2] if input_shape[2] is not None else None
#            return tensor_shape.TensorShape(
#                    [input_shape[0], height, width, input_shape[3]])
#
#    def call(self, inputs):
#        return backend.resize_images(
#                inputs, self.size[0], self.size[1], self.data_format,
#                interpolation=self.interpolation)
#
#    def get_config(self):
#        config = {
#                'size': self.size,
#                'data_format': self.data_format,
#                'interpolation': self.interpolation
#        }
#        base_config = super(UpSampling2D, self).get_config()
#        return dict(list(base_config.items()) + list(config.items()))

class BilinearUpsampling(Layer):
    """Just a simple bilinear upsampling layer. Works only with TF.
       Args:
           upsampling: tuple of 2 numbers > 0. The upsampling ratio for h and w
           output_size: used instead of upsampling arg if passed!
    """

    def __init__(self, upsampling=(2, 2), output_size=None, data_format=None, **kwargs):

        super(BilinearUpsampling, self).__init__(**kwargs)

        self.data_format = K.image_data_format()
        self.input_spec = InputSpec(ndim=4)
        if output_size:
            self.output_size = conv_utils.normalize_tuple(
                output_size, 2, 'output_size')
            self.upsampling = None
        else:
            self.output_size = None
            self.upsampling = conv_utils.normalize_tuple(
                upsampling, 2, 'upsampling')

    def compute_output_shape(self, input_shape):
        if self.upsampling:
            height = self.upsampling[0] * \
                input_shape[1] if input_shape[1] is not None else None
            width = self.upsampling[1] * \
                input_shape[2] if input_shape[2] is not None else None
        else:
            height = self.output_size[0]
            width = self.output_size[1]
        return (input_shape[0],
                height,
                width,
                input_shape[3])

    def call(self, inputs):
        if self.upsampling:
            if tf.__version__ < '2.0.0':
                return K.tf.image.resize_bilinear(inputs, (inputs.shape[1] * self.upsampling[0],
                                                           inputs.shape[2] * self.upsampling[1]),
                                                  align_corners=True)
            else:
                return tf.compat.v1.image.resize_bilinear(inputs, (inputs.shape[1] * self.upsampling[0],
                                                           inputs.shape[2] * self.upsampling[1]),
                                                  align_corners=True)
                tf.compat.v1.image.resize_bilinear
        else:
            if tf.__version__ < '2.0.0':
                return K.tf.image.resize_bilinear(inputs, (self.output_size[0],
                                                       self.output_size[1]),
                                              align_corners=True)
            else:
                return tf.compat.v1.image.resize_bilinear(inputs, (self.output_size[0],
                                                       self.output_size[1]),
                                              align_corners=True)

    def get_config(self):
        config = {'upsampling': self.upsampling,
                  'output_size': self.output_size,
                  'data_format': self.data_format}
        base_config = super(BilinearUpsampling, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


def SepConv_BN(x, filters, prefix, stride=1, kernel_size=3, rate=1, depth_activation=False, epsilon=1e-3):
    """ SepConv with BN between depthwise & pointwise. Optionally add activation after BN
        Implements right "same" padding for even kernel sizes
        Args:
            x: input tensor
            filters: num of filters in pointwise convolution
            prefix: prefix before name
            stride: stride at depthwise conv
            kernel_size: kernel size for depthwise convolution
            rate: atrous rate for depthwise convolution
            depth_activation: flag to use activation between depthwise & poinwise convs
            epsilon: epsilon to use in BN layer
    """
    if stride == 1:
        depth_padding = 'same'
    else:
        kernel_size_effective = kernel_size + (kernel_size - 1) * (rate - 1)
        pad_total = kernel_size_effective - 1
        pad_beg = pad_total // 2
        pad_end = pad_total - pad_beg
        x = ZeroPadding2D((pad_beg, pad_end))(x)
        depth_padding = 'valid'

    if not depth_activation:
        x = Activation('elu')(x)
    x = DepthwiseConv2D((kernel_size, kernel_size), strides=(stride, stride), dilation_rate=(rate, rate),
                        padding=depth_padding, use_bias=False, kernel_regularizer=l1_l2(1e-6, 1e-6), name=prefix + '_depthwise')(x)
    x = BatchNormalization(name=prefix + '_depthwise_BN', epsilon=epsilon)(x)
    if depth_activation:
        x = Activation('elu')(x)
    x = Conv2D(filters, (1, 1), padding='same',
               use_bias=False, kernel_regularizer=l1_l2(1e-6, 1e-6), name=prefix + '_pointwise')(x)
    x = BatchNormalization(name=prefix + '_pointwise_BN', epsilon=epsilon)(x)
    if depth_activation:
        x = Activation('elu')(x)

    return x


def _conv2d_same(x, filters, prefix, stride=1, kernel_size=3, rate=1):
    """Implements right 'same' padding for even kernel sizes
        Without this there is a 1 pixel drift when stride = 2
        Args:
            x: input tensor
            filters: num of filters in pointwise convolution
            prefix: prefix before name
            stride: stride at depthwise conv
            kernel_size: kernel size for depthwise convolution
            rate: atrous rate for depthwise convolution
    """
    if stride == 1:
        return Conv2D(filters,
                      (kernel_size, kernel_size),
                      strides=(stride, stride),
                      padding='same', use_bias=False,
                      dilation_rate=(rate, rate),
                      kernel_regularizer=l1_l2(1e-6, 1e-6),
                      name=prefix)(x)
    else:
        kernel_size_effective = kernel_size + (kernel_size - 1) * (rate - 1)
        pad_total = kernel_size_effective - 1
        pad_beg = pad_total // 2
        pad_end = pad_total - pad_beg
        x = ZeroPadding2D((pad_beg, pad_end))(x)
        return Conv2D(filters,
                      (kernel_size, kernel_size),
                      strides=(stride, stride),
                      padding='valid', use_bias=False,
                      dilation_rate=(rate, rate),
                      kernel_regularizer=l1_l2(1e-6, 1e-6),
                      name=prefix)(x)


def _xception_block(inputs, depth_list, prefix, skip_connection_type, stride,
                    rate=1, depth_activation=False, return_skip=False):
    """ Basic building block of modified Xception network
        Args:
            inputs: input tensor
            depth_list: number of filters in each SepConv layer. len(depth_list) == 3
            prefix: prefix before name
            skip_connection_type: one of {'conv','sum','none'}
            stride: stride at last depthwise conv
            rate: atrous rate for depthwise convolution
            depth_activation: flag to use activation between depthwise & pointwise convs
            return_skip: flag to return additional tensor after 2 SepConvs for decoder
            """
    #Reavle this block - turn itno actual inception block?
    residual = inputs
    if rate == 1:
        rate = [1, 1, 1]

    for i in range(3):
        residual = SepConv_BN(residual,
                              depth_list[i],
                              prefix + '_separable_conv{}'.format(i + 1),
                              stride=stride if i==2 else 1,
                              rate=rate[i], #Multi-grid (1, 2, 4)
                              depth_activation=depth_activation)
        if i == 1:
            skip = residual
    if skip_connection_type == 'conv':
        shortcut = _conv2d_same(inputs, depth_list[-1], prefix + '_shortcut',
                                kernel_size=1,
                                stride=stride)
        shortcut = BatchNormalization(name=prefix + '_shortcut_BN')(shortcut)
        outputs = layers.add([residual, shortcut])
    elif skip_connection_type == 'sum':
        outputs = layers.add([residual, inputs])
    elif skip_connection_type == 'none':
        outputs = residual
    if return_skip:
        return outputs, skip
    else:
        return outputs


def relu6(x):
    return K.relu(x, max_value=6)


def _make_divisible(v, divisor, min_value=None):
    if min_value is None:
        min_value = divisor
    new_v = max(min_value, int(v + divisor / 2) // divisor * divisor)
    # Make sure that round down does not go down by more than 10%.
    if new_v < 0.9 * v:
        new_v += divisor
    return new_v


def _inverted_res_block(inputs, expansion, stride, alpha, filters, block_id, skip_connection, rate=1):
    in_channels = inputs._keras_shape[-1]
    pointwise_conv_filters = int(filters * alpha)
    pointwise_filters = _make_divisible(pointwise_conv_filters, 8)
    x = inputs
    prefix = 'expanded_conv_{}_'.format(block_id)
    if block_id:
        # Expand

        x = Conv2D(expansion * in_channels, kernel_size=1, padding='same', 
                   use_bias=False, activation=None, kernel_regularizer=l1_l2(1e-6, 1e-6),
                   name=prefix + 'expand')(x)
        x = BatchNormalization(epsilon=1e-3, momentum=0.999,
                               name=prefix + 'expand_BN')(x)
        x = Activation(relu6, name=prefix + 'expand_relu')(x)
    else:
        prefix = 'expanded_conv_'
    # Depthwise
    x = DepthwiseConv2D(kernel_size=3, strides=stride, activation=None,
                        use_bias=False, padding='same', dilation_rate=(rate, rate), kernel_regularizer=l1_l2(1e-6, 1e-6),
                        name=prefix + 'depthwise')(x)
    x = BatchNormalization(epsilon=1e-3, momentum=0.999,
                           name=prefix + 'depthwise_BN')(x)

    x = Activation(relu6, name=prefix + 'depthwise_relu')(x)

    # Project
    x = Conv2D(pointwise_filters,
               kernel_size=1, padding='same', use_bias=False, activation=None, kernel_regularizer=l1_l2(1e-6, 1e-6),
               name=prefix + 'project')(x)
    x = BatchNormalization(epsilon=1e-3, momentum=0.999,
                           name=prefix + 'project_BN')(x)

    if skip_connection:
        return Add(name=prefix + 'add')([inputs, x])

    # if in_channels == pointwise_filters and stride == 1:
    #    return Add(name='res_connect_' + str(block_id))([inputs, x])

    return x


def Deeplabv3(weights='pascal_voc', input_tensor=None, input_shape=(512, 512, 3), classes=21, backbone='mobilenetv2', OS=16, alpha=1., atrous_rates = (1, 2, 3, 4, 5)):
    """ Instantiates the Deeplabv3+ architecture

    Optionally loads weights pre-trained
    on PASCAL VOC. This model is available for TensorFlow only,
    and can only be used with inputs following the TensorFlow
    data format `(width, height, channels)`.
    # Arguments
        weights: one of 'pascal_voc' (pre-trained on pascal voc)
            or None (random initialization)
        input_tensor: optional Keras tensor (i.e. output of `layers.Input()`)
            to use as image input for the model.
        input_shape: shape of input image. format HxWxC
            PASCAL VOC model was trained on (512,512,3) images
        classes: number of desired classes. If classes != 21,
            last layer is initialized randomly
        backbone: backbone to use. one of {'xception','mobilenetv2'}
        OS: determines input_shape/feature_extractor_output ratio. One of {8,16}.
            Used only for xception backbone.
        alpha: controls the width of the MobileNetV2 network. This is known as the
            width multiplier in the MobileNetV2 paper.
                - If `alpha` < 1.0, proportionally decreases the number
                    of filters in each layer.
                - If `alpha` > 1.0, proportionally increases the number
                    of filters in each layer.
                - If `alpha` = 1, default number of filters from the paper
                    are used at each layer.
            Used only for mobilenetv2 backbone

    # Returns
        A Keras model instance.

    # Raises
        RuntimeError: If attempting to run this model with a
            backend that does not support separable convolutions.
        ValueError: in case of invalid argument for `weights` or `backbone`

    """

    if not (weights in {'pascal_voc', 'cityscapes', None}):
        raise ValueError('The `weights` argument should be either '
                         '`None` (random initialization), `pascal_voc`, or `cityscapes` '
                         '(pre-trained on PASCAL VOC)')

    if K.backend() != 'tensorflow':
        raise RuntimeError('The Deeplabv3+ model is only available with '
                           'the TensorFlow backend.')

    if not (backbone in {'xception', 'mobilenetv2'}):
        raise ValueError('The `backbone` argument should be either '
                         '`xception`  or `mobilenetv2` ')

    if input_tensor is None:
        img_input = Input(shape=input_shape)
    else:
        if not K.is_keras_tensor(input_tensor):
            img_input = Input(tensor=input_tensor, shape=input_shape)
        else:
            img_input = input_tensor

    if OS == 8:
        entry_block3_stride = 1
        middle_block_rate = 2  # ! Not mentioned in paper, but required
        exit_block_rates = (2, 4)
        atrous_rates = (12, 24, 36)
    else:
        entry_block3_stride = 1 #2
        middle_block_rate = 1
        exit_block_rates = (2, 1)
        multi_grid = (1, 2, 4)
        #atrous_rates = (1, 2, 3, 4, 5) #TODO: 1 is the same as branch0 , CHANGE! #224
        #atrous_rates = (2, 3, 5, 8, 12) #448
#            atrous_rates = (2, 6, 12, 18) #old
#            atrous_rates = (6, 12, 18) #old

    x, skip1  = _xception_block(img_input, [128, 128, 128], 'entry_flow_block1', #224-112
                        skip_connection_type='conv', stride=2,
                        depth_activation=False, return_skip=True)
    x, skip2 = _xception_block(x, [256, 256, 256], 'entry_flow_block2',#112-56
                               skip_connection_type='conv', stride=2,
                               depth_activation=False, return_skip=True)
    x, skip3 = _xception_block(x, [728, 728, 728], 'entry_flow_block3',#56-28
                        skip_connection_type='conv', stride=2,
                        depth_activation=False, return_skip=True)
    skip6 = x #28
    for i in range(8):
        x = _xception_block(x, [728, 728, 728], 'middle_flow_unit_{}'.format(i + 1),
                            skip_connection_type='sum', stride=1, rate=1,
                            depth_activation=False)

    x = _xception_block(x, [728, 1024, 1024], 'exit_flow_block1',
                        skip_connection_type='conv', stride=2, rate=1,
                        depth_activation=False)
    x = _xception_block(x, [1536, 1536, 2048], 'exit_flow_block2',
                        skip_connection_type='none', stride=1, rate=multi_grid,
                        depth_activation=True)

    # end of feature extractor

    # branching for Atrous Spatial Pyrami>>>d Pooling

    # Image Feature branch
    #out_shape = int(np.ceil(input_shape[0] / OS))
    size_before = x.shape
    b4 = MaxPooling2D(pool_size=(2, 2))(x)
    b4 = Conv2D(256, (1, 1), padding='same',
                use_bias=False, kernel_regularizer=l1_l2(1e-6, 1e-6), name='image_pooling')(b4)
    b4 = BatchNormalization(name='image_pooling_BN', epsilon=1e-5)(b4)
    b4 = Activation('elu')(b4)
    b4 = BilinearUpsampling((2,2))(b4)
#    b4 = Lambda(lambda xx: K.tf.image.resize(xx, size_before[1:3], method='bilinear', align_corners=True))(b4)
#    b4 = UpSampling2D(size=(2, 2), interpolation="bilinear")(b4)

    # simple 1x1
    b0 = Conv2D(256, (1, 1), padding='same', use_bias=False, kernel_regularizer=l1_l2(1e-6, 1e-6), name='aspp0')(x)
    b0 = BatchNormalization(name='aspp0_BN', epsilon=1e-5)(b0)
    b0 = Activation('elu', name='aspp0_activation')(b0)

    # there are only 2 branches in mobilenetV2. not sure why
    if backbone == 'xception':
        # rate = 2 (12)
        b1 = SepConv_BN(x, 256, 'aspp1',
                        rate=atrous_rates[0], depth_activation=True, epsilon=1e-5)
        # rate = 3 (24)
        b2 = SepConv_BN(x, 256, 'aspp2',
                        rate=atrous_rates[1], depth_activation=True, epsilon=1e-5)
        # rate = 5 (36)
        b3 = SepConv_BN(x, 256, 'aspp3',
                        rate=atrous_rates[2], depth_activation=True, epsilon=1e-5)
        # rate = 10
        b5 = SepConv_BN(x, 256, 'aspp4',
                        rate=atrous_rates[3], depth_activation=True, epsilon=1e-5)
        # rate = 18
        b6 = SepConv_BN(x, 256, 'aspp5',
                        rate=atrous_rates[4], depth_activation=True, epsilon=1e-5)

        # concatenate ASPP branches & project
        x = Concatenate()([b4, b0, b1, b2, b3, b5, b6])
    else:
        x = Concatenate()([b4, b0])

    x = Conv2D(256, (1, 1), padding='same',
               use_bias=False, kernel_regularizer=l1_l2(1e-6, 1e-6), name='concat_projection')(x)
    x = BatchNormalization(name='concat_projection_BN', epsilon=1e-5)(x)
    x = Activation('elu')(x)
    x = Dropout(0.1)(x)

    # DeepLab v.3+ decoder

    if backbone == 'xception':
        # Feature projection
        # x4 (x2) block
        #x = Lambda(lambda xx: K.tf.image.resize(xx, skip3.shape[1:3], method='bilinear', align_corners=True))(x)
#        print(int(np.ceil(input_shape[0] / 4)))
        x = BilinearUpsampling(output_size=(int(np.ceil(input_shape[0] / 4)),
                                            int(np.ceil(input_shape[1] / 4))))(x)
#        x = UpSampling2D(size=(4, 4), interpolation="bilinear")(x)
        
        dec_skip1 = Conv2D(48, (1, 1), padding='same',
                           use_bias=False, kernel_regularizer=l1_l2(1e-6, 1e-6), name='feature_projection1')(skip3)
        dec_skip1 = BatchNormalization(
            name='feature_projection1_BN', epsilon=1e-5)(dec_skip1)
        dec_skip1 = Activation('elu')(dec_skip1)
        x = Concatenate()([x, dec_skip1])
        x = SepConv_BN(x, 256, 'decoder_conv1_0',
                       depth_activation=True, epsilon=1e-5)
        x = SepConv_BN(x, 256, 'decoder_conv1_1',
                       depth_activation=True, epsilon=1e-5)
        

    # you can use it with arbitary number of classes
    if classes == 21:
        last_layer_name = 'logits_semantic'
    else:
        last_layer_name = 'custom_logits_semantic'

    x = Conv2D(2, (1, 1), padding='same', kernel_regularizer=l1_l2(1e-6, 1e-6), name=last_layer_name)(x)
    x = BilinearUpsampling(output_size=(input_shape[0], input_shape[1]))(x)
#    x = UpSampling2D(size=(4, 4), interpolation="bilinear")(x)
    #size_before3 = img_input.shape
    #x = Lambda(lambda xx: tf.backend.resize_images(xx, size_before3[1:3], method='bilinear', align_corners=True))(x)

    out = Activation('sigmoid')(x)

    # Ensure that the model takes into account
    # any potential predecessors of `input_tensor`.
    if input_tensor is not None:
        inputs = get_source_inputs(input_tensor)
    else:
        inputs = img_input
    
    model = Model(inputs, out, name='deeplabv3plus')

    # load weights

    if weights == 'pascal_voc':
        if backbone == 'xception':
            weights_path = get_file('deeplabv3_xception_tf_dim_ordering_tf_kernels.h5',
                                    WEIGHTS_PATH_X,
                                    cache_subdir='models')
        else:
            weights_path = get_file('deeplabv3_mobilenetv2_tf_dim_ordering_tf_kernels.h5',
                                    WEIGHTS_PATH_MOBILE,
                                    cache_subdir='models')
        model.load_weights(weights_path, by_name=True)
    elif weights == 'cityscapes':
        if backbone == 'xception':
            weights_path = get_file('deeplabv3_xception_tf_dim_ordering_tf_kernels_cityscapes.h5',
                                    WEIGHTS_PATH_X_CS,
                                    cache_subdir='models')
        else:
            weights_path = get_file('deeplabv3_mobilenetv2_tf_dim_ordering_tf_kernels_cityscapes.h5',
                                    WEIGHTS_PATH_MOBILE_CS,
                                    cache_subdir='models')
        model.load_weights(weights_path, by_name=True)
    return model


def preprocess_input(x):
    """Preprocesses a numpy array encoding a batch of images.
    # Arguments
        x: a 4D numpy array consists of RGB values within [0, 255].
    # Returns
        Input array scaled to [-1.,1.]
    """
    return imagenet_utils.preprocess_input(x, mode='tf')

