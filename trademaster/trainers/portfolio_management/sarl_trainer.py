from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
from ..custom import Trainer
from ..builder import TRAINERS
from trademaster.utils import get_attr, save_object, load_object
import os
import ray
from ray.tune.registry import register_env
from trademaster.environments.portfolio_management.sarl_environment import PortfolioManagementSARLEnvironment
import pandas as pd
import numpy as np
import random
import torch


def env_creator(config):
    return PortfolioManagementSARLEnvironment(config)


def select_algorithms(alg_name):
    alg_name = alg_name.upper()
    if alg_name == "A2C":
        from ray.rllib.agents.a3c.a2c import A2CTrainer as trainer
    elif alg_name == "DDPG":
        from ray.rllib.agents.ddpg.ddpg import DDPGTrainer as trainer
    elif alg_name == 'PG':
        from ray.rllib.agents.pg import PGTrainer as trainer
    elif alg_name == 'PPO':
        from ray.rllib.agents.ppo.ppo import PPOTrainer as trainer
    elif alg_name == 'SAC':
        from ray.rllib.agents.sac import SACTrainer as trainer
    elif alg_name == 'TD3':
        from ray.rllib.agents.ddpg.ddpg import TD3Trainer as trainer
    else:
        print(alg_name)
        print(alg_name == "A2C")
        print(type(alg_name))
        raise NotImplementedError
    return trainer


@TRAINERS.register_module()
class PortfolioManagementSARLTrainer(Trainer):
    def __init__(self, **kwargs):
        super(PortfolioManagementSARLTrainer, self).__init__()

        self.device = get_attr(kwargs, "device", None)
        self.configs = get_attr(kwargs, "configs", None)
        self.agent_name = get_attr(kwargs, "agent_name", "ppo")
        self.epochs = get_attr(kwargs, "epochs", 20)
        self.dataset = get_attr(kwargs, "dataset", None)
        self.work_dir = get_attr(kwargs, "work_dir", None)

        ray.init(ignore_reinit_error=True)
        self.trainer_name = select_algorithms(self.agent_name)
        self.configs["env"] = PortfolioManagementSARLEnvironment
        self.configs["env_config"] = dict(dataset=self.dataset, task="train")
        register_env("portfolio_management", env_creator)

        self.seeds_list = get_attr(kwargs, "seeds_list", [12345])

        self.work_dir = os.path.join(ROOT, self.work_dir)
        if not os.path.exists(self.work_dir):
            os.makedirs(self.work_dir)

        self.checkpoints_path = os.path.join(self.work_dir, "checkpoints")
        if not os.path.exists(self.checkpoints_path):
            os.makedirs(self.checkpoints_path)

        self.set_seed(random.choice(self.seeds_list))

    def set_seed(self, seed):
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.benckmark = False
        torch.backends.cudnn.deterministic = True

    def train_and_valid(self):

        valid_score_list = []
        self.trainer = self.trainer_name(env="portfolio_management", config=self.configs)

        for epoch in range(1, self.epochs+1):
            print("Train Episode: [{}/{}]".format(epoch, self.epochs))
            self.trainer.train()

            config = dict(dataset=self.dataset, task="valid")
            self.valid_environment = env_creator(config)
            print("Valid Episode: [{}/{}]".format(epoch, self.epochs))
            state = self.valid_environment.reset()

            episode_reward_sum = 0
            while True:
                action = self.trainer.compute_single_action(state)
                state, reward, done, information = self.valid_environment.step(action)
                episode_reward_sum += reward
                if done:
                    print("Train Episode Reward Sum: {:04f}".format(episode_reward_sum))
                    break

            valid_score_list.append(information["sharpe_ratio"])

            checkpoint_path = os.path.join(self.checkpoints_path, "checkpoint-{:05d}.pkl".format(epoch))
            obj = self.trainer.save_to_object()
            save_object(obj, checkpoint_path)

        max_index = np.argmax(valid_score_list)
        obj = load_object(os.path.join(self.checkpoints_path, "checkpoint-{:05d}.pkl".format(max_index+1)))
        save_object(obj, os.path.join(self.checkpoints_path, "best.pkl"))
        ray.shutdown()

    def test(self):
        self.trainer = self.trainer_name(env="portfolio_management", config=self.configs)

        obj = load_object(os.path.join(self.checkpoints_path, "best.pkl"))
        self.trainer.restore_from_object(obj)

        config = dict(dataset=self.dataset, task="test")
        self.test_environment = env_creator(config)
        print("Test Best Episode")
        state = self.test_environment.reset()
        episode_reward_sum = 0
        while True:
            action = self.trainer.compute_single_action(state)
            state, reward, done, sharpe = self.test_environment.step(action)
            episode_reward_sum += reward
            if done:
                print("Test Best Episode Reward Sum: {:04f}".format(episode_reward_sum))
                break

        rewards = self.test_environment.save_asset_memory()
        assets = rewards["total assets"].values
        df_return = self.test_environment.save_portfolio_return_memory()
        daily_return = df_return.daily_return.values
        df = pd.DataFrame()
        df["daily_return"] = daily_return
        df["total assets"] = assets
        df.to_csv(os.path.join(self.work_dir, "test_result.csv"), index=False)
        return daily_return

    def style_test(self,style):
        self.trainer.restore(self.best_model_path)
        test_style_environments = []
        for i, path in enumerate(dataset.test_style_paths):
            config = dict(dataset=self.dataset, task="test_style",style_test_path=path,task_index=i)
            test_style_environments.append(env_creator(config))
        for i,env in enumerate(test_style_environments):
            state = env.reset()
            done = False
            while not done:
                action = self.trainer.compute_single_action(state)
                state, reward, done, sharpe = env.step(action)
            rewards = env.save_asset_memory()
            assets = rewards["total assets"].values
            df_return = env.save_portfolio_return_memory()
            daily_return = df_return.daily_return.values
            df = pd.DataFrame()
            df["daily_return"] = daily_return
            df["total assets"] = assets
            df.to_csv(os.path.join(self.work_dir, "test_style_result"+"style_"+str(style)+"_part_"+str(i)+".csv"), index=False)