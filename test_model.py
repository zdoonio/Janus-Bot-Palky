from stable_baselines3 import A2C
from stable_baselines3 import PPO
from sc2env import Sc2Env
from stable_baselines3.common.sb2_compat.rmsprop_tf_like import RMSpropTFLike 


LOAD_MODEL = "data/models/janusmind/v0_3_2.zip"
# Environment:
env = Sc2Env(is_train = False)

# load the model:
#model = A2C.load(LOAD_MODEL, env=env, policy_kwargs=dict(optimizer_class=RMSpropTFLike, optimizer_kwargs=dict(eps=1e-5)))

model = PPO('MlpPolicy', env, verbose=1)

# Play the game:
obs = env.reset()
done = False
while not done:
    action, _states = model.predict(obs)
    obs, rewards, dones, info = env.step(action)

