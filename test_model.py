from stable_baselines3 import A2C
from sc2env import Sc2Env


LOAD_MODEL = "data/models/janusmind/v0_3_1.zip"
# Environment:
env = Sc2Env(is_train = False)

# load the model:
model = A2C.load(LOAD_MODEL)


# Play the game:
obs = env.reset()
done = False
while not done:
    action, _states = model.predict(obs)
    obs, rewards, dones, info = env.step(action)

