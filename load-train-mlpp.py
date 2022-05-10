# $ source ~/Desktop/sc2env/bin/activate

# so this works, so far. 

from stable_baselines3 import PPO
import os
from sc2env import Sc2Env
import time
from wandb.integration.sb3 import WandbCallback
import wandb


LOAD_MODEL = "data/models/janusmind/v0_2_2.zip"
# Environment:
env = Sc2Env(is_train = True)

# load the model:
model = PPO.load(LOAD_MODEL, env=env)

model_name = f"janusmind"

models_dir = f"data/models/{model_name}/"
logdir = f"data/logs/{model_name}/"


conf_dict = {"Model": "v0.2.2",
             "Machine": "Main",
             "policy":"MlpPolicy",
             "model_save_name": model_name, 
             "load_model": LOAD_MODEL
             }

run = wandb.init(
    project=f'JanusBotv0.2',
    entity="zdoonio",
    config=conf_dict,
    sync_tensorboard=True,  # auto-upload sb3's tensorboard metrics
    save_code=True,  # save source code
)


# further train:
TIMESTEPS = 100
iters = 0
while True:
	print("On iteration: ", iters)
	iters += 1
	model.learn(total_timesteps=TIMESTEPS, reset_num_timesteps=False, tb_log_name=f"PPO")
	model.save(f"{models_dir}/v0_2_2.zip")