import torch.nn as nn
from models.encdec import Encoder, Decoder
from models.quantize_cnn import QuantizeEMAReset


class VQVAE_34(nn.Module):
    def __init__(self,
                 nb_code=1024,
                 code_dim=512,
                 output_emb_width=512,
                 down_t=3,
                 stride_t=2,
                 width=512,
                 depth=3,
                 dilation_growth_rate=3,
                 activation='relu',
                 norm=None):
        
        super().__init__()
        self.code_dim = code_dim
        self.num_code = nb_code
        self.encoder = Encoder(34, output_emb_width, down_t, stride_t, width, depth, dilation_growth_rate, activation=activation, norm=norm)
        self.decoder = Decoder(34, output_emb_width, down_t, stride_t, width, depth, dilation_growth_rate, activation=activation, norm=norm)
        self.quantizer = QuantizeEMAReset(nb_code, code_dim)

    def preprocess(self, x):
        # (bs, T, Jx3) -> (bs, Jx3, T)
        x = x.permute(0,2,1).float()
        return x

    def postprocess(self, x):
        # (bs, Jx3, T) ->  (bs, T, Jx3)
        x = x.permute(0,2,1)
        return x

    def encode(self, x):
        N, T, _ = x.shape
        x_in = self.preprocess(x)
        x_encoder = self.encoder(x_in)
        x_encoder = self.postprocess(x_encoder)
        x_encoder = x_encoder.contiguous().view(-1, x_encoder.shape[-1])  # (NT, C)
        code_idx = self.quantizer.quantize(x_encoder)
        code_idx = code_idx.view(N, -1)
        return code_idx

    def forward(self, x):
        
        x_in = self.preprocess(x)
        # Encode
        x_encoder = self.encoder(x_in)
        
        ## quantization
        x_quantized, loss, perplexity  = self.quantizer(x_encoder)

        ## decoder
        x_decoder = self.decoder(x_quantized)
        x_out = self.postprocess(x_decoder)
        return x_out, loss, perplexity

    def forward_decoder(self, x):
        x_d = self.quantizer.dequantize(x)
        x_d = x_d.view(1, -1, self.code_dim).permute(0, 2, 1).contiguous()
        
        # decoder
        x_decoder = self.decoder(x_d)
        x_out = self.postprocess(x_decoder)
        return x_out


class HumanoidVQVAE(nn.Module):
    def __init__(self,
                 nb_code=512,
                 code_dim=512,
                 output_emb_width=512,
                 down_t=3,
                 stride_t=2,
                 width=512,
                 depth=3,
                 dilation_growth_rate=3,
                 activation='relu',
                 norm=None):
        
        super().__init__()
        
        self.vqvae = VQVAE_34(nb_code, code_dim, output_emb_width, down_t, stride_t, width, depth, dilation_growth_rate, activation=activation, norm=norm)

    def encode(self, x):
        quants = self.vqvae.encode(x) # (N, T)
        return quants

    def forward(self, x):
        x_out, loss, perplexity = self.vqvae(x)
        return x_out, loss, perplexity

    def forward_decoder(self, x):
        x_out = self.vqvae.forward_decoder(x)
        return x_out
        