import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv as PGATConv

from graphmae.utils import create_activation


class GATConv(PGATConv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reset_parameters()

    def reset_parameters(self):
        # self.lin_src.reset_parameters()
        # self.lin_dst.reset_parameters()
        nn.init.xavier_normal_(self.lin_src.weight, gain=1.414)
        nn.init.xavier_normal_(self.lin_dst.weight, gain=1.414)

        nn.init.xavier_normal_(self.att_src, gain=1.414)
        nn.init.xavier_normal_(self.att_dst, gain=1.414)
        nn.init.constant_(self.bias, 0)


class GAT(nn.Module):
    def __init__(self,
                 in_dim,
                 num_hidden,
                 out_dim,
                 num_layers,
                 nhead,
                 nhead_out,
                 activation,
                 feat_drop,
                 attn_drop,
                 negative_slope,
                 residual,
                 norm,
                 concat_out=False,
                 encoding=False
                 ):
        super(GAT, self).__init__()
        self.out_dim = out_dim
        self.num_heads = nhead
        self.num_layers = num_layers
        self.gat_layers = nn.ModuleList()
        self.activation = activation
        self.concat_out = concat_out

        print(in_dim, num_hidden, out_dim, nhead, nhead_out, )
        self.feat_drop = feat_drop

        self.activation = nn.ModuleList([
            create_activation(activation) for _ in range(num_layers)
        ])
        self.last_activation = create_activation(activation) if encoding else None
        last_residual = (encoding and residual)
        last_norm = norm if encoding else None
        
        if num_layers == 1:
            self.gat_layers.append(GATConv(
                in_dim, out_dim, nhead_out,
                dropout=attn_drop, negative_slope=negative_slope, concat=concat_out, add_self_loops=False))
        else:
            # input projection (no residual)
            self.gat_layers.append(GATConv(
                in_dim, num_hidden, nhead,
                dropout=attn_drop, negative_slope=negative_slope, concat=concat_out, add_self_loops=False))
            # hidden layers
            for l in range(1, num_layers - 1):
                # due to multi-head, the in_dim = num_hidden * num_heads
                self.gat_layers.append(GATConv(
                    num_hidden * nhead, num_hidden, nhead,
                    dropout=attn_drop, negative_slope=negative_slope, concat=concat_out, add_self_loops=False))
            # output projection
            self.gat_layers.append(GATConv(
                num_hidden * nhead, out_dim, nhead_out,
                dropout=attn_drop, negative_slope=negative_slope, concat=concat_out, add_self_loops=False))
    
        self.head = nn.Identity()

    def forward(self, x, edge_index, return_hidden=False):
        h = x
        hidden_list = []
        for l in range(self.num_layers):
            h = F.dropout(h, p=self.feat_drop, training=self.training)
            h = self.gat_layers[l](h, edge_index)
            if l == self.num_layers-1:
                if self.last_activation:
                    h = self.last_activation(h)
            else:
                h = self.activation[l](h)
            hidden_list.append(h)
            # h = h.flatten(1)
        # output projection
        if return_hidden:
            return self.head(h), hidden_list
        else:
            return self.head(h)

    def reset_classifier(self, num_classes):
        self.head = nn.Linear(self.num_heads * self.out_dim, num_classes)
