# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

import dash_bootstrap_components as dbc
import hydra
from dash import Dash
from flask import Flask
from omegaconf import MISSING, DictConfig, OmegaConf
from settings.constants import RETRIEVAL, RETRIEVAL_FIELDS, UNDEFINED
from settings.visualization_config import VisualizationConfig

from nemo_skills.inference.prompt.few_shot_examples import examples_map
from nemo_skills.inference.prompt.utils import context_templates, get_prompt_config, prompt_types
from nemo_skills.utils import setup_logging

setup_logging()
config_path = os.path.join(os.path.abspath(Path(__file__).parents[1]), "settings")

config = {}


@hydra.main(version_base=None, config_path=config_path, config_name="visualization_config")
def set_config(cfg: VisualizationConfig) -> None:
    global config

    prompt_type = UNDEFINED  # TODO detect prompt_type

    prompt_types_without_extension = list(map(lambda name: name.split('.')[0], prompt_types))

    for name in prompt_types_without_extension:
        if asdict(get_prompt_config(name)) == cfg.prompt:
            prompt_type = name
            break

    if not cfg.data_file and not cfg.dataset and not cfg.split_name:
        cfg.data_file = UNDEFINED

    cfg.output_file = UNDEFINED

    def set_undefined(dict_cfg: Dict, cfg: DictConfig):
        for key, value in dict_cfg.items():
            if isinstance(value, Dict):
                setattr(cfg, key, set_undefined(value, getattr(cfg, key)))
            if value == MISSING:
                setattr(cfg, key, UNDEFINED)
        return cfg

    def get_specific_fields(dict_cfg: Dict, fields: List[Dict]) -> Dict:
        retrieved_values = {}
        for key, value in dict_cfg.items():
            if key in fields:
                retrieved_values[key] = value
            if isinstance(value, Dict):
                retrieved_values = {
                    **retrieved_values,
                    **get_specific_fields(value, fields),
                }
        return retrieved_values

    examples_types = list(examples_map.keys())
    examples_type = cfg.prompt.few_shot_examples.examples_type
    if examples_type == RETRIEVAL:
        cfg.prompt.few_shot_examples.examples_type = examples_types[0]

    cfg.prompt = set_undefined(OmegaConf.to_container(cfg.prompt), cfg.prompt)

    config['data_explorer'] = asdict(OmegaConf.to_object(cfg))
    if examples_type == RETRIEVAL:
        config['data_explorer']['prompt']['few_shot_examples']['examples_type'] = examples_type

    for param in ['host', 'ssh_server', 'ssh_key_path']:
        if param not in config['data_explorer']['sandbox'] and param in config['data_explorer']['server']:
            config['data_explorer']['sandbox'][param] = config['data_explorer']['server'][param]

    config['data_explorer']['prompt']['prompt_type'] = prompt_type

    config['data_explorer']['prompt']['context_template'] = context_templates[
        config['data_explorer']["prompt"]["context_type"]
    ]

    config['data_explorer']['types'] = {
        "prompt_type": [UNDEFINED] + prompt_types_without_extension,
        "examples_type": [UNDEFINED, RETRIEVAL] + examples_types,
        "context_type": [UNDEFINED] + list(context_templates.keys()),
        "retrieval_field": [""],
    }

    config['data_explorer']['retrieval_fields'] = get_specific_fields(config['data_explorer'], RETRIEVAL_FIELDS)

    config['data_explorer']['data_file'] = str(config['data_explorer']['data_file'])
    config['data_explorer']['generation_name'] = 'default_name'


set_config()
server = Flask(__name__)
server.config.update(config)

assets_path = os.path.join(os.path.dirname(__file__), 'assets')

app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    server=server,
    assets_folder=assets_path,
)

from callbacks.analyze_callbacks import choose_base_model
from callbacks.base_callback import nav_click
from callbacks.run_prompt_callbacks import add_example
