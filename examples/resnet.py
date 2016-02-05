#  Copyright 2015-present Scikit Flow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""
This example showcases how simple it is to build image classification networks.
It follows description from this TensorFlow tutorial:
    https://www.tensorflow.org/versions/master/tutorials/mnist/pros/index.html#deep-mnist-for-experts
"""

import random
from sklearn import metrics

import tensorflow as tf
from tensorflow.examples.tutorials.mnist import input_data

import skflow

from collections import namedtuple
from math import sqrt


"""Batch Normalization for TensorFlow.
Parag K. Mital, Jan 2016."""

class batch_normalize(object):
    """Basic usage from: http://stackoverflow.com/a/33950177

    Parag K. Mital, Jan 2016

    Attributes
    ----------
    batch_size : int
        Size of the batch.  Set to -1 to fit to current net.
    beta : Tensor
        A 1D beta Tensor with size matching the last dimension of t.
        An offset to be added to the normalized tensor.
    ema : tf.train.ExponentialMovingAverage
        For computing the moving average.
    epsilon : float
        A small float number to avoid dividing by 0.
    gamma : Tensor
        If "scale_after_normalization" is true, this tensor will be multiplied
        with the normalized tensor.
    momentum : float
        The decay to use for the moving average.
    name : str
        The variable scope for all variables under batch normalization.
    """

    def __init__(self, batch_size, epsilon=1e-5,
                 momentum=0.1, name="batch_norm"):
        """Summary

        Parameters
        ----------
        batch_size : int
            Size of the batch, or -1 for size to fit.
        epsilon : float, optional
            A small float number to avoid dividing by 0.
        momentum : float, optional
            Decay to use for the moving average.
        name : str, optional
            Variable scope will be under this prefix.
        """
        with tf.variable_scope(name) as scope:
            self.epsilon = epsilon
            self.momentum = momentum
            self.batch_size = batch_size
            self.ema = tf.train.ExponentialMovingAverage(decay=self.momentum)
            self.name = name

    def __call__(self, x, train=True):
        """Applies/updates the BN to the input Tensor.

        Parameters
        ----------
        x : Tensor
            The input tensor to normalize.
        train : bool, optional
            Whether or not to train parameters.

        Returns
        -------
        x_normed : Tensor
            The normalized Tensor.
        """
        shape = x.get_shape().as_list()

        # Using a variable scope means any new variables
        # will be prefixed with "variable_scope/", e.g.:
        # "variable_scope/new_variable".  Also, using
        # TensorBoard, this will make everything very
        # nicely grouped.
        with tf.variable_scope(self.name) as scope:
            self.gamma = tf.get_variable(
                "gamma", [shape[-1]],
                initializer=tf.random_normal_initializer(1., 0.02))
            self.beta = tf.get_variable(
                "beta", [shape[-1]],
                initializer=tf.constant_initializer(0.))

            mean, variance = tf.nn.moments(x, [0, 1, 2])

            return tf.nn.batch_norm_with_global_normalization(
                x, mean, variance, self.beta, self.gamma, self.epsilon,
                scale_after_normalization=True)


def conv2d(x, n_filters,
           k_h=5, k_w=5,
           stride_h=2, stride_w=2,
           stddev=0.02,
           batch_norm=False,
           activation=lambda x: x,
           bias=True,
           padding='SAME',
           name="Conv2D"):
    """2D Convolution with options for kernel size, stride, and init deviation.

    Parameters
    ----------
    x : Tensor
        Input tensor to convolve.
    n_filters : int
        Number of filters to apply.
    k_h : int, optional
        Kernel height.
    k_w : int, optional
        Kernel width.
    stride_h : int, optional
        Stride in rows.
    stride_w : int, optional
        Stride in cols.
    stddev : float, optional
        Initialization's standard deviation.
    activation : arguments, optional
        Function which applies a nonlinearity
    batch_norm : bool, optional
        Whether or not to apply batch normalization
    padding : str, optional
        'SAME' or 'VALID'
    name : str, optional
        Variable scope to use.

    Returns
    -------
    x : Tensor
        Convolved input.
    """
    with tf.variable_scope(name):
        w = tf.get_variable(
            'w', [k_h, k_w, x.get_shape()[-1], n_filters],
            initializer=tf.truncated_normal_initializer(stddev=stddev))
        conv = tf.nn.conv2d(
            x, w, strides=[1, stride_h, stride_w, 1], padding=padding)
        if bias:
            b = tf.get_variable(
                'b', [n_filters],
                initializer=tf.truncated_normal_initializer(stddev=stddev))
            conv = conv + b
        if batch_norm:
            norm = batch_normalize(-1)
            conv = norm(conv)
        return conv


def linear(x, n_units, scope=None, stddev=0.02,
           activation=lambda x: x):
    """Fully-connected network.

    Parameters
    ----------
    x : Tensor
        Input tensor to the network.
    n_units : int
        Number of units to connect to.
    scope : str, optional
        Variable scope to use.
    stddev : float, optional
        Initialization's standard deviation.
    activation : arguments, optional
        Function which applies a nonlinearity

    Returns
    -------
    x : Tensor
        Fully-connected output.
    """
    shape = x.get_shape().as_list()

    with tf.variable_scope(scope or "Linear"):
        matrix = tf.get_variable("Matrix", [shape[1], n_units], tf.float32,
                                 tf.random_normal_initializer(stddev=stddev))
        return activation(tf.matmul(x, matrix))

def residual_network(x, n_outputs,
                     activation=tf.nn.relu):
    """Builds a residual network.
    Parameters
    ----------
    x : Placeholder
        Input to the network
    n_outputs : TYPE
        Number of outputs of final softmax
    activation : Attribute, optional
        Nonlinearity to apply after each convolution
    Returns
    -------
    net : Tensor
        Description
    Raises
    ------
    ValueError
        If a 2D Tensor is input, the Tensor must be square or else
        the network can't be converted to a 4D Tensor.
    """
    # %%
    LayerBlock = namedtuple(
        'LayerBlock', ['num_layers', 'num_filters', 'bottleneck_size'])
    blocks = [LayerBlock(3, 128, 32),
              LayerBlock(3, 256, 64),
              LayerBlock(3, 512, 128),
              LayerBlock(3, 1024, 256)]

    # %%
    input_shape = x.get_shape().as_list()
    if len(input_shape) == 2:
        ndim = int(sqrt(input_shape[1]))
        if ndim * ndim != input_shape[1]:
            raise ValueError('input_shape should be square')
        x = tf.reshape(x, [-1, ndim, ndim, 1])

    # %%
    # First convolution expands to 64 channels and downsamples
    net = conv2d(x, 64, k_h=7, k_w=7,
                 batch_norm=True, name='conv1',
                 activation=activation)

    # %%
    # Max pool and downsampling
    net = tf.nn.max_pool(
        net, [1, 3, 3, 1], strides=[1, 2, 2, 1], padding='SAME')

    # %%
    # Setup first chain of resnets
    net = conv2d(net, blocks[0].num_filters, k_h=1, k_w=1,
                 stride_h=1, stride_w=1, padding='VALID', name='conv2')

    # %%
    # Loop through all res blocks
    for block_i, block in enumerate(blocks):
        for layer_i in range(block.num_layers):

            name = 'block_%d/layer_%d' % (block_i, layer_i)
            conv = conv2d(net, block.num_filters, k_h=1, k_w=1,
                          padding='VALID', stride_h=1, stride_w=1,
                          activation=activation, batch_norm=True,
                          name=name + '/conv_in')

            conv = conv2d(conv, block.bottleneck_size, k_h=3, k_w=3,
                          padding='SAME', stride_h=1, stride_w=1,
                          activation=activation, batch_norm=True,
                          name=name + '/conv_bottleneck')

            conv = conv2d(conv, block.num_filters, k_h=1, k_w=1,
                          padding='VALID', stride_h=1, stride_w=1,
                          activation=activation, batch_norm=True,
                          name=name + '/conv_out')

            net = conv + net
        try:
            # upscale to the next block size
            next_block = blocks[block_i + 1]
            net = conv2d(net, next_block.num_filters, k_h=1, k_w=1,
                         padding='SAME', stride_h=1, stride_w=1, bias=False,
                         name='block_%d/conv_upscale' % block_i)
        except IndexError:
            pass

    # %%
    net = tf.nn.avg_pool(net,
                         ksize=[1, net.get_shape().as_list()[1],
                                net.get_shape().as_list()[2], 1],
                         strides=[1, 1, 1, 1], padding='VALID')
    net = tf.reshape(
        net,
        [-1, net.get_shape().as_list()[1] *
         net.get_shape().as_list()[2] *
         net.get_shape().as_list()[3]])

    net = linear(net, n_outputs, activation=tf.nn.softmax)

    # %%
    return net


### Download and load MNIST data.

mnist = input_data.read_data_sets('MNIST_data', one_hot=True)


x = tf.placeholder(tf.float32, [None, 784])
y = tf.placeholder(tf.float32, [None, 10])
y_pred = residual_network(x, 10)

# %% Define loss/eval/training functions
cross_entropy = -tf.reduce_sum(y * tf.log(y_pred))
optimizer = tf.train.AdamOptimizer().minimize(cross_entropy)

# %% Monitor accuracy
correct_prediction = tf.equal(tf.argmax(y_pred, 1), tf.argmax(y, 1))
accuracy = tf.reduce_mean(tf.cast(correct_prediction, 'float'))

# %% We now create a new session to actually perform the initialization the
# variables:
sess = tf.Session()
sess.run(tf.initialize_all_variables())

# %% We'll train in minibatches and report accuracy:
batch_size = 50
n_epochs = 5
for epoch_i in range(n_epochs):
    # Training
    train_accuracy = 0
    for batch_i in range(mnist.train.num_examples // batch_size):
        batch_xs, batch_ys = mnist.train.next_batch(batch_size)
        train_accuracy += sess.run([optimizer, accuracy], feed_dict={
            x: batch_xs, y: batch_ys})[1]
    train_accuracy /= (mnist.train.num_examples // batch_size)

    # Validation
    valid_accuracy = 0
    for batch_i in range(mnist.validation.num_examples // batch_size):
        batch_xs, batch_ys = mnist.validation.next_batch(batch_size)
        valid_accuracy += sess.run(accuracy,
                                   feed_dict={
                                       x: batch_xs,
                                       y: batch_ys
                                   })
    valid_accuracy /= (mnist.validation.num_examples // batch_size)
    print('epoch:', epoch_i, ', train:',
          train_accuracy, ', valid:', valid_accuracy)





# ### Convolutional network

# def max_pool_2x2(tensor_in):
#     return tf.nn.max_pool(tensor_in, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1],
#         padding='SAME')

# def conv_model(X, y):
#     X = tf.reshape(X, [-1, 28, 28, 1])
#     with tf.variable_scope('conv_layer1'):
#         h_conv1 = skflow.ops.conv2d(X, n_filters=32, filter_shape=[5, 5], 
#                                     bias=True, activation=tf.nn.relu)
#         h_pool1 = max_pool_2x2(h_conv1)
#     with tf.variable_scope('conv_layer2'):
#         h_conv2 = skflow.ops.conv2d(h_pool1, n_filters=64, filter_shape=[5, 5], 
#                                     bias=True, activation=tf.nn.relu)
#         h_pool2 = max_pool_2x2(h_conv2)
#         h_pool2_flat = tf.reshape(h_pool2, [-1, 7 * 7 * 64])
#     h_fc1 = skflow.ops.dnn(h_pool2_flat, [1024], activation=tf.nn.relu, keep_prob=0.5)
#     return skflow.models.logistic_regression(h_fc1, y)

# classifier = skflow.TensorFlowEstimator(
#     model_fn=conv_model, n_classes=10, batch_size=100, steps=20000,
#     learning_rate=0.001)
# classifier.fit(mnist.train.images, mnist.train.labels)
# score = metrics.accuracy_score(mnist.test.labels, classifier.predict(mnist.test.images))
# print('Accuracy: {0:f}'.format(score))
