import gym
from gym import spaces
import numpy as np
import subprocess
import pickle
import time
import os

class Sc2Env(gym.Env):
	"""Custom Environment that follows gym interface"""
	def __init__(self, is_train):
		super(Sc2Env, self).__init__()
		# Define action and observation space
		# They must be gym.spaces objects
		# Example when using discrete actions:
		self.action_space = spaces.Discrete(22)
		self.observation_space = spaces.Box(low=0, high=255,
											shape=(160, 160, 3), dtype=np.uint8)
		self.is_train = is_train

	def step(self, action):
		wait_for_action = True
		# waits for action.
		while wait_for_action:
			#print("waiting for action")
			try:
				with open('data/state_rwd_action.pkl', 'rb') as f:
					state_rwd_action = pickle.load(f)

					if state_rwd_action['action'] is not None:
						#print("No action yet")
						wait_for_action = True
					else:
						#print("Needs action")
						wait_for_action = False
						state_rwd_action['action'] = action
						with open('data/state_rwd_action.pkl', 'wb') as f:
							# now we've added the action.
							pickle.dump(state_rwd_action, f)
			except Exception as e:
				print(str(e))
				pass

		# waits for the new state to return (map and reward) (no new action yet. )
		wait_for_state = True
		while wait_for_state:
			try:
				if os.path.getsize('data/state_rwd_action.pkl') > 0:
					with open('data/state_rwd_action.pkl', 'rb') as f:
						state_rwd_action = pickle.load(f)
						if state_rwd_action['action'] is None:
							#print("No state yet")
							wait_for_state = True
						else:
							#print("Got state state")
							state = state_rwd_action['state']
							reward = state_rwd_action['reward']
							done = state_rwd_action['done']
							wait_for_state = False

			except Exception as e:
				wait_for_state = True   
				map = np.zeros((160, 160, 3), dtype=np.uint8)
				observation = map
				data = {"state": map, "reward": 0, "action": 3, "done": False}  # empty action waiting for the next one!
				with open('data/state_rwd_action.pkl', 'wb') as f:
					pickle.dump(data, f)

				state = map
				reward = 0
				done = False
				action = 22

		info ={}
		observation = state
		return observation, reward, done, info


	def reset(self):
		map = np.zeros((160, 160, 3), dtype=np.uint8)
		observation = map
		data = {"state": map, "reward": 0, "action": None, "done": False}  # empty action waiting for the next one!
		with open('data/state_rwd_action.pkl', 'wb') as f:
			pickle.dump(data, f)

		if self.is_train:
			print("RESETTING ENVIRONMENT!!!!!!!!!!!!!")
      		# run incredibot-sct.py non-blocking:
			subprocess.Popen(['python', 'run_train.py'])
   
		return observation  # reward, done, info can't be included
