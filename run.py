
import sc2, sys
from ladder import run_ladder_game
from sc2.data import Race, Difficulty
from sc2.player import Bot, Computer
from sc2.main import run_game
from stable_baselines3 import PPO
from sc2env import Sc2Env

from janusbot import JanusBot
bot = Bot(Race.Protoss, JanusBot(), 'JanusBot')

# Start game
if __name__ == '__main__':
    subprocess.Popen(['python', 'test_model.py'])
    if "--LadderServer" in sys.argv:
        # Ladder game started by LadderManager
        print("Starting ladder game...")
        result, opponentid = run_ladder_game(bot)
        print(result," against opponent ", opponentid)
    else:
        # Local game
        print("Starting local game...")
        run_game(sc2.maps.get("2000AtmospheresAIE"), [
            bot,
            Computer(Race.Protoss, Difficulty.VeryHard)
        ], realtime=True)