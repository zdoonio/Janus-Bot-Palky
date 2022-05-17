from stable_baselines3 import A2C
import os
from sc2env import Sc2Env
import time
from wandb.integration.sb3 import WandbCallback
from stable_baselines3.common.sb2_compat.rmsprop_tf_like import RMSpropTFLike 
import wandb


model_name = f"janusmind"

models_dir = f"data/models/{model_name}/"
logdir = f"data/logs/{model_name}/"


conf_dict = {"Model": "v0.3.1",
             "Machine": "Main",
             "policy":"MlpPolicy",
             "model_save_name": model_name}


run = wandb.init(
    project=f'JanusBot',
    entity="zdoonio",
    config=conf_dict,
    sync_tensorboard=True,  # auto-upload sb3's tensorboard metrics
    save_code=True,  # optional
)


if not os.path.exists(models_dir):
	os.makedirs(models_dir)

if not os.path.exists(logdir):
	os.makedirs(logdir)

env = Sc2Env(is_train = True)

model = A2C('MlpPolicy', env, verbose=1, tensorboard_log=logdir, policy_kwargs=dict(optimizer_class=RMSpropTFLike, optimizer_kwargs=dict(eps=1e-5)))

TIMESTEPS = 10
iters = 0
while True:
	print("On iteration: ", iters)
	iters += 1
	model.learn(total_timesteps=TIMESTEPS, reset_num_timesteps=False, tb_log_name=f"A2C")
	model.save(f"{models_dir}/v0_3_1.zip")
