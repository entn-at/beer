
'''Implementation of various Multi-Layer Perceptron with specific
final layer corresponding to the parameters of a distribution.
This kind of MLP are used with model combining deep neural network
and bayesian model (Variational Auto-Encoder and its variant).

'''

import abc
import math
import torch
from torch import nn
from torch.autograd import Variable

from .normal import NormalDiagonalCovariance


def _normal_diag_natural_params(mean, var):
    '''Transform the standard parameters of a Normal (diag. cov.) into
    their canonical forms.

    Note:
        The (negative) log normalizer is appended to it.

    '''
    return torch.cat([
        -1. / (2 * var),
        mean / var,
        -(mean ** 2) / (2 * var),
        -.5 * torch.log(var)
    ], dim=-1)


def _structure_output_dim(structure):
    'Find the output dimension of a given structure.'
    for transform in reversed(structure):
        if isinstance(transform, nn.Linear):
            s_out_dim = transform.out_features
            break
    return s_out_dim


class MLPModel(nn.Module, metaclass=abc.ABCMeta):
    '''Base class for the encoder / decoder neural network of
    the VAE. The output of this network are the parameters of a
    conjugate exponential model.

    '''

    def __init__(self, structure, outputs):
        '''Initialize the ``MLPModel``.

        Args:
            structure (``torch.Sequential``): Sequence linear/
                non-linear operations.
            outputs (list): List of output dimension for the
                parameters of the model.

        '''
        super().__init__()
        self.structure = structure
        s_out_dim = _structure_output_dim(structure)
        self.output_layer = nn.ModuleList()
        for i, outdim in enumerate(outputs):
            self.output_layer.append(nn.Linear(s_out_dim, outdim))

    def forward(self, X):
        h = self.structure(X)
        outputs = [transform(h) for transform in self.output_layer]
        return outputs


class MLPNormalDiag(MLPModel):
    '''Neural-Network ending with a double linear projection
    providing the mean and the logarithm of the diagonal of the
    covariance matrix.

    '''

    def __init__(self, structure, dim):
        '''Initialize a ``MLPNormalDiag`` object.

        Args:
            structure (``torch.Sequential``): Sequence linear/
                non-linear operations.
            dim (int): Desired dimension of the modeled random
                variable.

        '''
        super().__init__(structure, [dim, dim])

    def forward(self, X):
        mean, logvar = super().forward(X)
        return MLPStateNormalDiagonalCovariance(mean, torch.exp(logvar))


class MLPNormalIso(MLPModel):
    '''Neural-Network ending with a double linear projection
    providing the mean and the isotropic covariance matrix.

    '''

    def __init__(self, structure, dim):
        '''Initialize a ``MLPNormalDiag`` object.

        Args:
            structure (``torch.Sequential``): Sequence linear/
                non-linear operations.
            dim (int): Desired dimension of the modeled random
                variable.

        '''
        super().__init__(structure, [dim, 1])

    def forward(self, X):
        mean, logvar = super().forward(X)
        ones = Variable(torch.ones(mean.size(1)).type(X.type()))
        return MLPStateNormalDiagonalCovariance(mean, ones * torch.exp(logvar))


class MLPStateNormalDiagonalCovariance:

    def __init__(self, mean, var):
        self.mean = mean
        self.var = var

    def entropy(self):
        'Compute the per-frame entropy of the posterior distribution.'
        nparams = _normal_diag_natural_params(self.mean, self.var)
        exp_T = NormalDiagonalCovariance.sufficient_statistics_from_mean_var(
            self.mean, self.var)
        return - (nparams * exp_T).sum(dim=-1)

