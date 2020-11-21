import click
import numpy as np
import PIL.Image
import torch
import torch.nn as nn
import torchvision.models

from .assets import Asset
from .tags import Tag


class Model(nn.Module):

    def __init__(self,
                 num_features,
                 num_labels,
                 num_hidden_pixels=1024,
                 num_hidden_features=1024,
                 num_hidden_fc=1024):
        super(Model, self).__init__()

        self.image = torchvision.models.resnet152(pretrained=True)
        self.image.fc = nn.Linear(self.image.fc.in_features, num_hidden_pixels)

        self.features = nn.Sequential(
            nn.Linear(num_features, num_hidden_features),
            nn.SiLU(),
            nn.Linear(num_hidden_features, num_hidden_features))

        self.fc = nn.Sequential(
            nn.Linear(num_hidden_pixels + num_hidden_features, num_hidden_fc),
            nn.SiLU(),
            nn.Linear(num_hidden_fc, num_labels),
            nn.Sigmoid())

    def forward(self, image, features):
        return self.fc(torch.cat((self.image(image), self.features(features)), dim=1))


class Dataset(torch.utils.data.Dataset):

    def __init__(self, assets, feature_tags, label_tags):
        self.assets = assets
        self.feature_tags = feature_tags
        self.label_tags = label_tags

    def __len__(self):
        return len(self.assets)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.to_list()

        asset = self.assets[idx]
        pixels = torch.from_numpy(self.convert_image(self.load_image(asset)))
        features = torch.tensor([t in asset['tags'] for t in self.feature_tags])
        labels = torch.tensor([t in asset['tags'] for t in self.label_tags])
        return pixels.float(), features.float(), labels.int()

    def load_image(self, asset):
        square = PIL.Image.new('RGB', (224, 224), (0, 0, 0))
        try:
            img = PIL.Image.open(asset['path']).convert('RGB')
        except:
            return square
        # http://stackoverflow.com/q/4228530
        # https://magnushoff.com/articles/jpeg-orientation/
        for op in {
                2: [PIL.Image.FLIP_LEFT_RIGHT],
                3: [PIL.Image.ROTATE_180],
                4: [PIL.Image.FLIP_TOP_BOTTOM],
                5: [PIL.Image.ROTATE_90, PIL.Image.FLIP_TOP_BOTTOM],
                6: [PIL.Image.ROTATE_270],
                7: [PIL.Image.ROTATE_270, PIL.Image.FLIP_TOP_BOTTOM],
                8: [PIL.Image.ROTATE_90],
        }.get(asset['orientation'], ()):
            img = img.transpose(op)
        img.thumbnail((224, 224), PIL.Image.BICUBIC)
        w, h = img.size
        if w == 224 and h == 224:
            return img
        square.paste(img, ((224 - w) // 2, (224 - h) // 2))
        return square

    def convert_image(self, image):
        means = np.asarray([0.485, 0.456, 0.406])
        stdevs = np.asarray([0.229, 0.224, 0.225])
        return ((np.asarray(image) / 255.0 - means) / stdevs).transpose(2, 0, 1)


def agg_stats(predictions, labels, stats):
    eps = 1e-6
    return dict(k=stats.get('k', eps) + labels.numel(),
                p=stats.get('p', eps) + labels.sum(),
                tp=stats.get('tp', eps) + (predictions * labels).sum(),
                fn=stats.get('fn', eps) + ((1 - predictions) * labels).sum(),
                tn=stats.get('tn', eps) + ((1 - predictions) * (1 - labels)).sum(),
                fp=stats.get('fp', eps) + (predictions * (1 - labels)).sum())


def log_stats(label, stats):
    tpr = 100 * stats['tp'] / stats['p']
    tnr = 100 * stats['tn'] / (stats['k'] - stats['p'])
    ppv = 100 * stats['tp'] / (stats['tp'] + stats['fp'])
    npv = 100 * stats['tn'] / (stats['tn'] + stats['fn'])
    acc = 100 * (stats['tn'] + stats['tp']) / stats['k']
    print(f'{label}: acc {acc:.1f}% tpr {tpr:.1f}% tnr {tnr:.1f}% ppv {ppv:.1f}% npv {npv:.1f}%')


def train(epochs, train, valid, feature_tags, label_tags):
    '''
    '''
    def pbar(assets):
        return click.progressbar(
            length=len(assets) // 16, label='Processing', width=0, fill_char='█')

    def dataset(assets):
        return torch.utils.data.DataLoader(
            Dataset(assets, feature_tags, label_tags),
            batch_size=16,
            shuffle=True,
            num_workers=12)

    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

    training, validation = dataset(train), dataset(valid)

    model = Model(len(feature_tags), len(label_tags)).to(device)

    criterion = torch.nn.MultiLabelSoftMarginLoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.001, momentum=0.9)
    scheduler = torch.optim.lr_scheduler.StepLR(
        optimizer, step_size=3, gamma=0.7, verbose=True)

    for e in range(epochs):
        print(f'Epoch {e+1}:')

        model.train()
        stats = {}
        with pbar(train) as bar:
            for pixels, features, labels in training:
                outputs = model(pixels.to(device), features.to(device))
                labels = labels.to(device)
                optimizer.zero_grad()
                criterion(outputs, labels).backward()
                optimizer.step()
                stats = agg_stats((outputs > 0.5).int(), labels, stats)
                bar.update(1)
        log_stats('train', stats)

        model.eval()
        stats = {}
        with pbar(valid) as bar:
            for pixels, features, labels in validation:
                with torch.no_grad():
                    outputs = model(pixels.to(device), features.to(device))
                    labels = labels.to(device)
                    stats = agg_stats((outputs > 0.5).int(), labels, stats)
                bar.update(1)
        log_stats('valid', stats)

        scheduler.step()

    return model
