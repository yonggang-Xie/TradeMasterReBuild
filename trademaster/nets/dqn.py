import torch
import torch.nn as nn

from .builder import NETS
from .custom import Net
from torch import Tensor

def build_mlp(dims: [int]) -> nn.Sequential:  # MLP (MultiLayer Perceptron)
    net_list = []
    for i in range(len(dims) - 1):
        net_list.extend([nn.Linear(dims[i], dims[i + 1]), nn.ReLU()])
    del net_list[-1]  # remove the activation of output layer
    return nn.Sequential(*net_list)

@NETS.register_module()
class QNet(Net):
    def __init__(self, dims: [int], state_dim: int, action_dim: int, explore_rate = 0.25):
        super().__init__()
        self.net = build_mlp(dims=[state_dim, *dims, action_dim])
        self.explore_rate = explore_rate
        self.action_dim = action_dim 
        self.net.apply(self.init_weights)
        
        #uncomment to see weights
#         for name, param in self.net.named_parameters():
#             print(f"Layer: {name} | Size: {param.size()} | Values : {param[:2]} \n")       

    def forward(self, state: Tensor) -> Tensor:
        return self.net(state)  # Q values for multiple actions

    def get_action(self, state: Tensor) -> Tensor:  # return the index [int] of discrete action for exploration
        if self.explore_rate < torch.rand(1):
            action = self.net(state).argmax(dim=1, keepdim=True)
        else:
            action = torch.randint(self.action_dim, size=(state.shape[0], 1))
        return action
     
    def init_weights(self,m):
        if isinstance(m, nn.Linear):
            torch.nn.init.kaiming_uniform(m.weight)
            m.bias.data.zero_()

