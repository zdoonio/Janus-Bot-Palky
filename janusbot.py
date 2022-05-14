import random
from typing import List
from loguru import logger
from sc2.bot_ai import BotAI  # parent class we inherit from
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.buff_id import BuffId
from sc2.ids.ability_id import AbilityId
from sc2.unit import Unit
from sc2.position import Point2
import pickle
import cv2
import math
import numpy as np
import time


class JanusBot(BotAI):  # inhereits from BotAI (part of BurnySC2)

    SAVE_REPLAY = True
    proxy_built = False
    shaded = False
    shades_mapping = {}

    total_steps = 10000
    steps_for_pun = np.linspace(0, 1, total_steps)
    step_punishment = ((np.exp(steps_for_pun**3) / 10) - 0.1) * 10

    def do_random_attack(self, unit: Unit):
        invisible_enemy_start_locations = [
            p for p in self.enemy_start_locations if not self.is_visible(p)]
        if self.enemy_structures:
            unit.attack(self.enemy_structures.random.position)
        elif any(invisible_enemy_start_locations):
            unit.attack(random.choice(invisible_enemy_start_locations))
        else:
            area = self.game_info.playable_area
            target = np.random.uniform(
                (area.x, area.y), (area.right, area.top))
            target = Point2(target)
            if self.in_pathing_grid(target) and not self.is_visible(target):
                unit.attack(target)

    def flee_to_base(self, unit_type: UnitTypeId):
        if self.units(unit_type).idle.amount > 0:
            for unit in self.units(unit_type):
                unit.attack(self.start_location)

    def scout(self, curent_iteration: int):
        # are there any idle probes:
        try:
            self.last_sent
        except:
            self.last_sent = 0

        # if self.last_sent doesnt exist yet:
        if (curent_iteration - self.last_sent) > 400:
            try:
                if self.units(UnitTypeId.PROBE).idle.exists:
                    # pick one of these randomly:
                    probe = random.choice(self.units(UnitTypeId.PROBE).idle)
                    self.do_random_attack(probe)
                else:
                    probe = random.choice(self.units(UnitTypeId.PROBE))
                    self.do_random_attack(probe)
                    # send probe towards enemy base:

                self.last_sent = curent_iteration
            except Exception as e:
                pass

    def train_troop_in_building(self, building_type: UnitTypeId, troop_type: UnitTypeId) -> None:
        # might amount of each unit should be limited ? and self.units(UnitTypeId.ZEALOT).amount < 16
        if self.can_afford(troop_type):
            for gate in self.structures(building_type).ready.idle:
                if self.can_afford(troop_type):
                    gate.train(troop_type)

    def train_voidray(self) -> None:
        if self.can_afford(UnitTypeId.VOIDRAY) and self.units(UnitTypeId.VOIDRAY).amount < 12:
            for sg in self.structures(UnitTypeId.STARGATE).ready.idle:
                if self.can_afford(UnitTypeId.VOIDRAY):
                    sg.train(UnitTypeId.VOIDRAY)

    async def expand(self) -> None:
        found_something = False
        if self.supply_left < 4:
            # build pylons.
            if self.already_pending(UnitTypeId.PYLON) == 0:
                if self.can_afford(UnitTypeId.PYLON):
                    await self.build(UnitTypeId.PYLON, near=random.choice(self.townhalls))
                    found_something = True

        if not found_something:

            for nexus in self.townhalls:
                # get worker count for this nexus:
                worker_count = len(self.workers.closer_than(10, nexus))
                if worker_count < 22:  # 16+3+3
                    if nexus.is_idle and self.can_afford(UnitTypeId.PROBE):
                        nexus.train(UnitTypeId.PROBE)
                        found_something = True

                # have we built enough assimilators?
                # find vespene geysers
                for geyser in self.vespene_geyser.closer_than(10, nexus):
                    # build assimilator if there isn't one already:
                    if not self.can_afford(UnitTypeId.ASSIMILATOR):
                        break
                    if not self.structures(UnitTypeId.ASSIMILATOR).closer_than(2.0, geyser).exists:
                        await self.build(UnitTypeId.ASSIMILATOR, geyser)
                        found_something = True

            if not found_something:
                if self.already_pending(UnitTypeId.NEXUS) == 0 and self.can_afford(UnitTypeId.NEXUS):
                    await self.expand_now()

    async def build_advanced_building(self, building_one: UnitTypeId, building_two: UnitTypeId, close_to_one: int, close_to_two: int, build_cybernetics: bool = True) -> None:
        # iterate thru all nexus and see if these buildings are close
        for nexus in self.townhalls:
            # is there is not a gateway close:
            if not self.structures(UnitTypeId.GATEWAY).closer_than(10, nexus).exists:
                # if we can afford it:
                if self.can_afford(UnitTypeId.GATEWAY) and self.already_pending(UnitTypeId.GATEWAY) == 0:
                    # build gateway
                    await self.build(UnitTypeId.GATEWAY, near=nexus)

            # if the is not a cybernetics core close:
            if build_cybernetics:
                await self.build_building_close_to_nexus(
                    nexus, UnitTypeId.CYBERNETICSCORE, 100)

            # build advanced building one:
            await self.build_building_close_to_nexus(
                nexus, building_one, close_to_one)

            # build advanced building two:
            await self.build_building_close_to_nexus(
                nexus, building_two, close_to_two)

    async def build_building_close_to_nexus(self, nexus: Unit, unit_type: UnitTypeId, close_to: int):
        if not self.structures(unit_type).closer_than(close_to, nexus).exists:
            # if we can afford it:
            if self.can_afford(unit_type) and self.already_pending(unit_type) == 0:
                # build cybernetics core
                await self.build(unit_type, near=nexus)

    async def build_proxy_pylon(self, curent_iteration: int):
        # await self.chat_send("(probe)(pylon) building proxy pylon")
        try:
            self.last_proxy
        except:
            self.last_proxy = 0

        point = self.game_info.map_center.towards(
            self.enemy_start_locations[0], 20)

        if (self.structures(UnitTypeId.CYBERNETICSCORE).amount >= 1 and not self.proxy_built and self.can_afford(UnitTypeId.PYLON)) and (curent_iteration - self.last_sent) > 200:
            await self.build(UnitTypeId.PYLON, near=point)
            self.proxy_built = True

        if(not self.structures(UnitTypeId.PYLON).closer_than(20, point).exists):
            self.proxy_built = False

    async def build_more_gates(self):
        if self.structures(UnitTypeId.PYLON).exists:
            pylon = self.structures(UnitTypeId.PYLON).ready
            # If we have no cyber core, build one
            if not self.structures(UnitTypeId.CYBERNETICSCORE):
                if (self.can_afford(UnitTypeId.CYBERNETICSCORE) and self.already_pending(UnitTypeId.CYBERNETICSCORE) == 0):
                    await self.build(UnitTypeId.CYBERNETICSCORE, near=pylon)
            # Build up to 2 gates
            if (self.can_afford(UnitTypeId.GATEWAY) and self.structures(UnitTypeId.WARPGATE).amount + self.structures(UnitTypeId.GATEWAY).amount < 2):
                await self.build(UnitTypeId.GATEWAY, near=pylon)

    async def warp_new_units(self, ability: AbilityId, unit_type: UnitTypeId, proxy: Unit) -> None:
        for warpgate in self.structures(UnitTypeId.WARPGATE).ready:
            abilities = await self.get_available_abilities(warpgate)
            # all the units have the same cooldown anyway so let's just look at ZEALOT
            if ability in abilities:
                pos = proxy.position.to2.random_on_distance(4)
                placement = await self.find_placement(ability, pos, placement_step=1)
                if placement is None:
                    # return ActionResult.CantFindPlacementLocation
                    print("can't place")
                    return
                warpgate.warp_in(unit_type, placement)

    # on_step is a method that is called every step of the game.
    async def on_step(self, iteration: int):
        if iteration == 0:
            await self.chat_send("(glhf)")

        if not any(self.townhalls):
            # surrender
            await self.client.chat_send('(gg)', False)
            #await self.client.quit()

        no_action = True

        while no_action:
            try:
                with open('data/state_rwd_action.pkl', 'rb') as f:
                    state_rwd_action = pickle.load(f)

                    if state_rwd_action['action'] is None:
                        #print("No action yet")
                        no_action = True
                    else:
                        #print("Action found")
                        no_action = False
            except:
                pass

        await self.distribute_workers()  # put idle workers back to work

        action = state_rwd_action['action']
        # await BotAction.take_action(action, iteration) this block might be moved
        '''
        0: expand (ie: move to next spot, or build to 16 (minerals)+3 assemblers+3)
        1: build stargate (or up to one) (evenly)
        2: build proxy pylon
        3: build more gates
        4: build dark shrine
        5: build defences eg. photon cannon
        6: train zealtos
        7: train voidray (evenly)
        8: train zealots in warp gate
        9: train stalkers in warp gate
        10: train dark templars in warp gate
        11: send scout (evenly/random/closest to enemy?)
        12: do upgrades
        13: chronoboost nexus or cybernetics
        14: defend attack
        15: attack dark templars / zealots
        16: attack stalker units
        17: attack voidray (known buildings, units, then enemy base, just go in logical order.)
        18: zealots flee (back to base)
        19: voidray flee (back to base)
        20: cannon rush
        21: micro stalkers
        22: find adept shades
        23: flee probes when attacked
        24: if enemy being aggresive build oracle 
        25: attack oracle
        '''

        # 0: expand (ie: move to next spot, or build to 16 (minerals)+3 assemblers+3)
        if action == 0:
            try:
                await self.expand()
            except Exception as e:
                print(e)

        # 1: build stargate (or up to one) (evenly)
        elif action == 1:
            try:
                await self.build_advanced_building(UnitTypeId.STARGATE, UnitTypeId.STARGATE, 100, 20, build_cybernetics=True)
            except Exception as e:
                print("Action 1", e)

        # 2: build proxy pylon
        elif action == 2:
            try:
                await self.build_proxy_pylon(iteration)
            except Exception as e:
                print("Action 2", e)

        # 3: build more gates
        elif action == 3:
            try:
                await self.build_more_gates()
            except Exception as e:
                print("Action 3", e)

        # 4: build dark shrine
        elif action == 4:
            try:
                await self.build_advanced_building(UnitTypeId.TWILIGHTCOUNCIL, UnitTypeId.DARKSHRINE, 100, 100)
            except Exception as e:
                print("Action 4", e)

        # 5: build defences eg. photon cannon
        elif action == 5:
            try:
                await self.build_advanced_building(UnitTypeId.FORGE, UnitTypeId.PHOTONCANNON, 100, 15)
            except Exception as e:
                print("Action 5", e)

        # 6: train zealtos
        elif action == 6:
            try:
                self.train_troop_in_building(
                    UnitTypeId.GATEWAY, UnitTypeId.ZEALOT)
            except Exception as e:
                print("Action 6", e)

        # 7: train voidray (evenly)
        elif action == 7:
            try:
                self.train_troop_in_building(
                    UnitTypeId.STARGATE, UnitTypeId.VOIDRAY)
            except Exception as e:
                print("Action 7", e)

        # 8: train zealots in warp gate
        elif action == 8:
            try:
                targets = (self.enemy_units).filter(
                    lambda unit: unit.can_be_attacked)
                if self.proxy_built and self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 1:
                    proxy = self.structures(UnitTypeId.PYLON).closest_to(
                        self.enemy_start_locations[0])
                    await self.warp_new_units(AbilityId.WARPGATETRAIN_ZEALOT, UnitTypeId.ZEALOT, proxy)
                elif not self.proxy_built and self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 1 and targets.closer_than(25, self.start_location).exists:
                    random_nexus_pylon = self.structures(
                        UnitTypeId.PYLON).closest_to(self.townhalls.random)
                    await self.warp_new_units(AbilityId.WARPGATETRAIN_ZEALOT, UnitTypeId.ZEALOT, random_nexus_pylon)
            except Exception as e:
                print("Action 8", e)

        # 9: train stalkers in warp gate
        elif action == 9:
            try:
                targets = (self.enemy_units).filter(
                    lambda unit: unit.can_be_attacked)
                if self.proxy_built and self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 1:
                    proxy = self.structures(UnitTypeId.PYLON).closest_to(
                        self.enemy_start_locations[0])
                    await self.warp_new_units(AbilityId.WARPGATETRAIN_STALKER, UnitTypeId.STALKER, proxy)
                elif not self.proxy_built and self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 1 and targets.closer_than(25, self.start_location).exists:
                    random_nexus_pylon = self.structures(
                        UnitTypeId.PYLON).closest_to(self.townhalls.random)
                    await self.warp_new_units(AbilityId.WARPGATETRAIN_STALKER, UnitTypeId.STALKER, random_nexus_pylon)
            except Exception as e:
                print("Action 9", e)

        # 10: train dark templars in warp gate
        elif action == 10:
            try:
                targets = (self.enemy_units).filter(
                    lambda unit: unit.can_be_attacked)
                if self.proxy_built and self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 1:
                    proxy = self.structures(UnitTypeId.PYLON).closest_to(
                        self.enemy_start_locations[0])
                    await self.warp_new_units(AbilityId.WARPGATETRAIN_DARKTEMPLAR, UnitTypeId.DARKTEMPLAR, proxy)
                elif not self.proxy_built and self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 1 and targets.closer_than(25, self.start_location).exists:
                    random_nexus_pylon = self.structures(
                        UnitTypeId.PYLON).closest_to(self.townhalls.random)
                    await self.warp_new_units(AbilityId.WARPGATETRAIN_DARKTEMPLAR, UnitTypeId.DARKTEMPLAR, random_nexus_pylon)
            except Exception as e:
                print("Action 10", e)

        # 11: send scout (evenly/random/closest to enemy?)
        elif action == 11:
            try:
                self.scout(curent_iteration=iteration)
            except Exception as e:
                print("Action 11", e)

        # 12: do upgrades,
        # now it is simple version just do level one upgrades
        # TODO: add multiple upgrades and calculate costs
        elif action == 12:
            try:
                for forge in self.structures(UnitTypeId.FORGE).ready.idle:
                    if self.can_afford(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL1):
                        forge.research(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL1)
                    if self.can_afford(UpgradeId.PROTOSSGROUNDARMORSLEVEL1):
                        forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL1)
                    if self.can_afford(UpgradeId.PROTOSSSHIELDSLEVEL1):
                        forge.research(UpgradeId.PROTOSSSHIELDSLEVEL1)
                    if self.can_afford(UpgradeId.PROTOSSGROUNDARMORSLEVEL2):
                        forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL2)
                    if self.can_afford(UpgradeId.PROTOSSGROUNDARMORSLEVEL2):
                        forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL2)
                    if self.can_afford(UpgradeId.PROTOSSSHIELDSLEVEL2):
                        forge.research(UpgradeId.PROTOSSSHIELDSLEVEL2)

                if (self.structures(UnitTypeId.CYBERNETICSCORE).ready and self.can_afford(AbilityId.RESEARCH_WARPGATE) and self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 0):
                    ccore = self.structures(
                        UnitTypeId.CYBERNETICSCORE).ready.first
                    ccore.research(UpgradeId.WARPGATERESEARCH)
                    
                if (self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready and self.can_afford(AbilityId.RESEARCH_CHARGE)):
                    council = self.structures(
                        UnitTypeId.TWILIGHTCOUNCIL).ready.first
                    council.research(UpgradeId.RESEARCH_CHARGE)    

                # Morph to warp gate when research is complete
                for gateway in self.structures(UnitTypeId.GATEWAY).ready.idle:
                    if self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 1:
                        gateway(AbilityId.MORPH_WARPGATE)

            except Exception as e:
                print("Action 12", e)

        # 13: chronoboost nexus or cybernetics core
        elif action == 13:
            try:
                for nexus in self.structures(UnitTypeId.NEXUS):
                    if not self.structures(UnitTypeId.CYBERNETICSCORE).ready:
                        if not nexus.has_buff(BuffId.CHRONOBOOSTENERGYCOST) and not nexus.is_idle:
                            if nexus.energy >= 50:
                                nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, nexus)
                    else:
                        ccore = self.structures(
                            UnitTypeId.CYBERNETICSCORE).ready.first
                        if not ccore.has_buff(BuffId.CHRONOBOOSTENERGYCOST) and not ccore.is_idle:
                            if nexus.energy >= 50:
                                nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, ccore)
            except Exception as e:
                print("Action 13", e)

        # 14: defend attack try to use zealots
        elif action == 14:
            try:
                targets = (self.enemy_units).filter(
                    lambda unit: unit.can_be_attacked)
                for nexus in self.structures(UnitTypeId.NEXUS):
                    self.is_attack = targets.closer_than(10, nexus)
                for zealot in self.units(UnitTypeId.ZEALOT):
                    if(zealot.is_idle and self.is_attack):
                        target = targets.closest_to(zealot)
                        zealot.attack(target)
            except Exception as e:
                print("Action 14", e)

        # 15: attack dark templars
        # Make stalkers attack either closest enemy unit or enemy spawn location
        elif action == 15:
            try:
                if self.units(UnitTypeId.DARKTEMPLAR).amount > 2:
                    for templar in self.units(UnitTypeId.DARKTEMPLAR | UnitTypeId.ZEALOT).ready.idle:
                        targets = (self.enemy_units | self.enemy_structures).filter(
                            lambda unit: unit.can_be_attacked)
                        if targets:
                            target = targets.closest_to(templar)
                            templar.attack(target)
                        else:
                            self.do_random_attack(templar)

            except Exception as e:
                print("Action 15", e)

        # 16: attack stalker units
        # Make stalkers attack either closest enemy unit or enemy spawn location
        elif action == 16:
            try:
                if self.units(UnitTypeId.STALKER).amount > 6:
                    for stalker in self.units(UnitTypeId.STALKER).ready.idle:
                        targets = (self.enemy_units | self.enemy_structures).filter(
                            lambda unit: unit.can_be_attacked)
                        if targets:
                            target = targets.closest_to(stalker)
                            stalker.attack(target)
                        else:
                            self.do_random_attack(stalker)

            except Exception as e:
                print("Action 16", e)

        # 17: attack voidray (known buildings, units, then enemy base, just go in logical order.)
        elif action == 17:
            try:
                targets = (self.enemy_units).filter(
                    lambda unit: unit.can_be_attacked)
                if targets.closer_than(20, self.start_location):
                    for voidray in self.units(UnitTypeId.VOIDRAY):
                        target = targets.closest_to(voidray)
                        voidray.attack(target)
                # If we have at least 5 void rays, attack closes enemy unit/building, or if none is visible: attack move towards enemy spawn
                elif self.units(UnitTypeId.VOIDRAY).amount > 5:
                    for voidray in self.units(UnitTypeId.VOIDRAY):
                        # Activate charge ability if the void ray just attacked
                        if voidray.weapon_cooldown > 0:
                            voidray(AbilityId.EFFECT_VOIDRAYPRISMATICALIGNMENT)
                        # Choose target and attack, filter out invisible targets
                        targets = (self.enemy_units | self.enemy_structures)
                        if targets:
                            target = targets.closest_to(voidray)
                            voidray.attack(target)
                        else:
                            self.do_random_attack(voidray)

            except Exception as e:
                print("Action 17", e)

        # 18: zealots flee
        # TODO: think about more complex algorythm for flee for eg. count chances to being attack
        elif action == 18:
            try:
                self.flee_to_base(UnitTypeId.ZEALOT)
            except Exception as e:
                print("Action 18", e)

        # 19: voidray flee
        # TODO: think about more complex algorythm for flee for eg. count chances to being attack
        elif action == 19:
            try:
                self.flee_to_base(UnitTypeId.VOIDRAY)
            except Exception as e:
                print("Action 19", e)

        # 20: cannon rush
        # TODO: maybe do more complex tactics for cannon rush
        elif action == 20:
            try:
                self.last_proxy
            except:
                self.last_proxy = 0

            try:
                # await self.chat_send("(probe)(pylon)(cannon)(cannon)(gg)")
                if not self.townhalls:
                    # Attack with all workers if we don't have any nexuses left, attack-move on enemy spawn (doesn't work on 4 player map) so that probes auto attack on the way
                    for worker in self.workers:
                        worker.attack(self.enemy_start_locations[0])
                    return
                else:
                    nexus = self.townhalls.random

                location = self.enemy_structures.closer_than(
                    30, self.enemy_start_locations[0]).exists

                # Make probes until we have 24 total
                if self.supply_workers < 24 and nexus.is_idle:
                    if self.can_afford(UnitTypeId.PROBE):
                        nexus.train(UnitTypeId.PROBE)

                # If we have no pylon, build one near starting nexus
                elif not self.structures(UnitTypeId.PYLON) and self.already_pending(UnitTypeId.PYLON) == 0:
                    if self.can_afford(UnitTypeId.PYLON):
                        await self.build(UnitTypeId.PYLON, near=nexus)

                # If we have no forge, build one near the pylon that is closest to our starting nexus
                elif not self.structures(UnitTypeId.FORGE):
                    pylon_ready = self.structures(UnitTypeId.PYLON).ready
                    if pylon_ready:
                        if self.can_afford(UnitTypeId.FORGE):
                            await self.build(UnitTypeId.FORGE, near=pylon_ready.closest_to(nexus))

                # If we have less than 2 pylons, build one at the enemy base
                elif self.structures(UnitTypeId.PYLON).amount < 2 and (iteration - self.last_proxy) > 100:
                    if self.can_afford(UnitTypeId.PYLON):
                        pos = self.enemy_start_locations[0].towards(
                            self.game_info.map_center, random.randrange(25, 35))
                        await self.build(UnitTypeId.PYLON, near=pos)

                # If we have no cannons but at least 2 completed pylons, automatically find a placement location and build them near enemy start location
                elif not self.structures(UnitTypeId.PHOTONCANNON).closer_than(35, self.enemy_start_locations[0]):
                    if self.structures(UnitTypeId.PYLON).ready.amount >= 2 and self.can_afford(UnitTypeId.PHOTONCANNON):
                        pylon = self.structures(UnitTypeId.PYLON).closer_than(
                            35, self.enemy_start_locations[0]).random
                        await self.build(UnitTypeId.PHOTONCANNON, near=pylon)

                # Decide if we should make pylon or cannons, then build them at random location near enemy spawn
                elif self.can_afford(UnitTypeId.PYLON) and self.can_afford(UnitTypeId.PHOTONCANNON) and location:
                    # Ensure "fair" decision
                    for _ in range(20):
                        pos = self.enemy_start_locations[0].random_on_distance(
                            random.randrange(10, 25))
                        building = UnitTypeId.PHOTONCANNON if self.state.psionic_matrix.covers(
                            pos) else UnitTypeId.PYLON
                        await self.build(building, near=pos)

            except Exception as e:
                print("Action 20", e)

        # 21: micro stalkers
        elif action == 21:
            try:
                if self.units(UnitTypeId.STALKER).amount > 3:
                    stalkers = self.units(UnitTypeId.STALKER)
                    enemy_location = self.enemy_start_locations[0]

                    if self.structures(UnitTypeId.PYLON).ready:
                        pylon = self.structures(
                            UnitTypeId.PYLON).closest_to(enemy_location)

                        for stalker in stalkers:
                            if stalker.weapon_cooldown == 0:
                                stalker.attack(enemy_location)
                            elif stalker.weapon_cooldown < 0:
                                stalker.move(pylon)
                            else:
                                stalker.move(pylon)
            except Exception as e:
                print("Action 21", e)

        # 22: find adepts shades
        elif action == 22:
            try:
                adepts = self.units(UnitTypeId.ADEPT)
                if adepts and not self.shaded:
                    # Wait for adepts to spawn and then cast ability
                    for adept in adepts:
                        adept(AbilityId.ADEPTPHASESHIFT_ADEPTPHASESHIFT,
                              self._game_info.map_center)
                    self.shaded = True
                elif self.shades_mapping:
                    # Debug log and draw a line between the two units
                    for adept_tag, shade_tag in self.shades_mapping.items():
                        adept = self.units.find_by_tag(adept_tag)
                        shade = self.units.find_by_tag(shade_tag)
                        if shade:
                            logger.info(
                                f"Remaining shade time: {shade.buff_duration_remain} / {shade.buff_duration_max}")
                        if adept and shade:
                            self.client.debug_line_out(
                                adept, shade, (0, 255, 0))
                    logger.info(self.shades_mapping)
                elif self.shaded:
                    # Find shades
                    shades = self.units(UnitTypeId.ADEPTPHASESHIFT)
                    for shade in shades:
                        remaining_adepts = adepts.tags_not_in(
                            self.shades_mapping)
                        # Figure out where the shade should have been "self.client.game_step"-frames ago
                        forward_position = Point2(
                            (shade.position.x + math.cos(shade.facing),
                             shade.position.y + math.sin(shade.facing))
                        )
                        previous_shade_location = shade.position.towards(
                            forward_position, -
                            (self.client.game_step / 16) * shade.movement_speed
                        )  # See docstring of movement_speed attribute
                        closest_adept = remaining_adepts.closest_to(
                            previous_shade_location)
                        self.shades_mapping[closest_adept.tag] = shade.tag
            except Exception as e:
                print("Action 22", e)

        map = np.zeros(
            (self.game_info.map_size[0], self.game_info.map_size[1], 3), dtype=np.uint8)

        # draw the minerals:
        for mineral in self.mineral_field:
            pos = mineral.position
            c = [175, 255, 255]
            fraction = mineral.mineral_contents / 1800
            if mineral.is_visible:
                print(mineral.mineral_contents)
                map[math.ceil(pos.y)][math.ceil(pos.x)] = [
                    int(fraction*i) for i in c]
            else:
                map[math.ceil(pos.y)][math.ceil(pos.x)] = [20, 75, 50]

        # draw the enemy start location:
        for enemy_start_location in self.enemy_start_locations:
            pos = enemy_start_location
            c = [0, 0, 255]
            map[math.ceil(pos.y)][math.ceil(pos.x)] = c

        # draw the enemy units:
        for enemy_unit in self.enemy_units:
            pos = enemy_unit.position
            c = [100, 0, 255]
            # get unit health fraction:
            fraction = enemy_unit.health / \
                enemy_unit.health_max if enemy_unit.health_max > 0 else 0.0001
            map[math.ceil(pos.y)][math.ceil(pos.x)] = [
                int(fraction*i) for i in c]

        # draw the enemy structures:
        for enemy_structure in self.enemy_structures:
            pos = enemy_structure.position
            c = [0, 100, 255]
            # get structure health fraction:
            fraction = enemy_structure.health / \
                enemy_structure.health_max if enemy_structure.health_max > 0 else 0.0001
            map[math.ceil(pos.y)][math.ceil(pos.x)] = [
                int(fraction*i) for i in c]

        # draw our structures:
        for our_structure in self.structures:
            # if it's a nexus:
            if our_structure.type_id == UnitTypeId.NEXUS:
                pos = our_structure.position
                c = [255, 255, 175]
                # get structure health fraction:
                fraction = our_structure.health / \
                    our_structure.health_max if our_structure.health_max > 0 else 0.0001
                map[math.ceil(pos.y)][math.ceil(pos.x)] = [
                    int(fraction*i) for i in c]

            else:
                pos = our_structure.position
                c = [0, 255, 175]
                # get structure health fraction:
                fraction = our_structure.health / \
                    our_structure.health_max if our_structure.health_max > 0 else 0.0001
                map[math.ceil(pos.y)][math.ceil(pos.x)] = [
                    int(fraction*i) for i in c]

        # draw the vespene geysers:
        for vespene in self.vespene_geyser:
            # draw these after buildings, since assimilators go over them.
            # tried to denote some way that assimilator was on top, couldnt
            # come up with anything. Tried by positions, but the positions arent identical. ie:
            # vesp position: (50.5, 63.5)
            # bldg positions: [(64.369873046875, 58.982421875), (52.85693359375, 51.593505859375),...]
            pos = vespene.position
            c = [255, 175, 255]
            fraction = vespene.vespene_contents / 2250

            if vespene.is_visible:
                map[math.ceil(pos.y)][math.ceil(pos.x)] = [
                    int(fraction*i) for i in c]
            else:
                map[math.ceil(pos.y)][math.ceil(pos.x)] = [50, 20, 75]

        # draw our units:
        for our_unit in self.units:
            # if it is a voidray:
            if our_unit.type_id == UnitTypeId.VOIDRAY:
                pos = our_unit.position
                c = [255, 75, 75]
                # get health:
                fraction = our_unit.health / our_unit.health_max if our_unit.health_max > 0 else 0.0001
                map[math.ceil(pos.y)][math.ceil(pos.x)] = [
                    int(fraction*i) for i in c]

            else:
                pos = our_unit.position
                c = [175, 255, 0]
                # get health:
                fraction = our_unit.health / our_unit.health_max if our_unit.health_max > 0 else 0.0001
                map[math.ceil(pos.y)][math.ceil(pos.x)] = [
                    int(fraction*i) for i in c]

        # show map with opencv, resized to be larger:
        # horizontal flip:

        cv2.imshow('map', cv2.flip(cv2.resize(map, None, fx=4,
                   fy=4, interpolation=cv2.INTER_NEAREST), 0))
        cv2.waitKey(1)

        if self.SAVE_REPLAY:
            # save map image into "replays dir"
            cv2.imwrite(f"replays/{int(time.time())}-{iteration}.png", map)

        reward = 0

        try:
            attack_count = 0
            # iterate through our void rays:
            for voidray in self.units(UnitTypeId.VOIDRAY):
                # if voidray is attacking and is in range of enemy unit:
                if voidray.is_attacking and voidray.target_in_range:
                    if self.enemy_units.closer_than(8, voidray) or self.enemy_structures.closer_than(8, voidray):
                        # reward += 0.005 # original was 0.005, decent results, but let's 3x it.
                        reward += 0.015
                        attack_count += 1

            # iterate through our photon cannon:
            for cannon in self.structures(UnitTypeId.PHOTONCANNON):
                # if voidray is attacking and is in range of enemy unit:
                if cannon.is_attacking and cannon.target_in_range:
                    if self.enemy_units.closer_than(8, cannon) or self.enemy_structures.closer_than(8, cannon):
                        # reward += 0.005 # original was 0.005, decent results, but let's 3x it.
                        reward += 0.01
                        attack_count += 1

            # iterate through our stalkers:
            for stalker in self.units(UnitTypeId.STALKER):
                # if voidray is attacking and is in range of enemy unit:
                if stalker.is_attacking and stalker.target_in_range:
                    if self.enemy_units.closer_than(8, stalker) or self.enemy_structures.closer_than(8, stalker):
                        # reward += 0.005 # original was 0.005, decent results, but let's 3x it.
                        reward += 0.015
                        attack_count += 1

            # iterate through our zealots:
            for zealot in self.units(UnitTypeId.ZEALOT):
                # if voidray is attacking and is in range of enemy unit:
                if zealot.is_attacking and zealot.target_in_range:
                    if self.enemy_units.closer_than(8, zealot) or self.enemy_structures.closer_than(8, zealot):
                        # reward += 0.005 # original was 0.005, decent results, but let's 3x it.
                        reward += 0.01
                        attack_count += 1

            # iterate through our zealots:
            for templar in self.units(UnitTypeId.DARKTEMPLAR):
                # if voidray is attacking and is in range of enemy unit:
                if templar.is_attacking and templar.target_in_range:
                    if self.enemy_units.closer_than(8, templar) or self.enemy_structures.closer_than(8, templar):
                        # reward += 0.005 # original was 0.005, decent results, but let's 3x it.
                        reward += 0.015
                        attack_count += 1

        except Exception as e:
            print("reward", e)
            reward = 0

        if iteration % 100 == 0:
            print(
                f"Iter: {iteration}. RWD: {reward}. Z: {self.units(UnitTypeId.ZEALOT).amount} S: {self.units(UnitTypeId.STALKER).amount} DT: {self.units(UnitTypeId.DARKTEMPLAR).amount} VR: {self.units(UnitTypeId.VOIDRAY).amount}")

        save_map = np.resize(map, (224, 224, 3))

        # write the file:
        data = {"state": save_map, "reward": reward, "action": None,
                "done": False}  # empty action waiting for the next one!

        with open('data/state_rwd_action.pkl', 'wb') as f:
            pickle.dump(data, f)
