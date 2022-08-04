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
#import cv2
import math
import numpy as np
import time


class JanusBot(BotAI):  # inhereits from BotAI (part of BurnySC2)

    SAVE_REPLAY = True
    proxy_built = False
    shaded = False
    shades_mapping = {}
    siege = False

    total_steps = 10000
    steps_for_pun = np.linspace(0, 1, total_steps)
    step_punishment = ((np.exp(steps_for_pun**3) / 10) - 0.1) * 10
    current_tactic = 0
    
    # bot can use multiple tactics to perform win:
    # 1: Reaper rush
    # 2: Proxy Barracks
    def choose_tactic(self): 
        self.current_tactic = random.randrange(1, 2)
                 
        
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
                
    def flee_to_ramp(self, unit_type: UnitTypeId):
        if self.units(unit_type).idle.amount > 0:
            for unit in self.units(unit_type):
                unit.attack(self.main_base_ramp.protoss_wall_warpin)            

    def scout(self, curent_iteration: int):
        # are there any idle probes:
        try:
            self.last_sent
        except:
            self.last_sent = 0

        # if self.last_sent doesnt exist yet:
        if (curent_iteration - self.last_sent) > 250:
            try:
                if self.units(UnitTypeId.SCV).idle.exists:
                    # pick one of these randomly:
                    scv = random.choice(self.units(UnitTypeId.SCV).idle)
                    self.do_random_attack(scv)
                else:
                    scv = random.choice(self.units(UnitTypeId.SCV))
                    self.do_random_attack(scv)
                    # send probe towards enemy base:

                self.last_sent = curent_iteration
            except Exception as e:
                pass

    def train_troop_in_building(self, building_type: UnitTypeId, troop_type: UnitTypeId) -> None:
        if self.can_afford(troop_type):
            for rax in self.structures(building_type).ready.idle:
                if self.can_afford(troop_type):
                    rax.train(troop_type)   

    async def expand(self) -> None:
        found_something = False
        if self.supply_left < 4:
            # build pylons.
            if self.already_pending(UnitTypeId.SCV) == 0:
                if self.can_afford(UnitTypeId.SCV):
                    await self.build(UnitTypeId.SCV, near=random.choice(self.townhalls))
                    found_something = True

        if not found_something:

            for cc in self.townhalls:
                # get worker count for this nexus:
                worker_count = len(self.workers.closer_than(10, cc))
                if worker_count < 22:  # 16+3+3
                    if cc.is_idle and self.can_afford(UnitTypeId.SCV):
                        cc.train(UnitTypeId.SCV)
                        found_something = True

                # have we built enough assimilators?
                # find vespene geysers
                for geyser in self.vespene_geyser.closer_than(10, nexus):
                    # build assimilator if there isn't one already:
                    if not self.can_afford(UnitTypeId.RAFINERY):
                        break
                    if not self.structures(UnitTypeId.RAFINERY).closer_than(2.0, geyser).exists:
                        await self.build(UnitTypeId.RAFINERY, geyser)
                        found_something = True

            if not found_something:
                if self.already_pending(UnitTypeId.COMMANDCENTER) == 0 and self.can_afford(UnitTypeId.COMMANDCENTER):
                    await self.expand_now()

    async def build_building_close_to_cc(self, cc: Unit, unit_type: UnitTypeId, close_to: int):
        if not self.structures(unit_type).closer_than(close_to, cc).exists:
            # if we can afford it:
            if self.can_afford(unit_type) and self.already_pending(unit_type) == 0:
                # build cybernetics core
                await self.build(unit_type, near=cc)

    async def build_proxy_rax(self, curent_iteration: int):
        try:
            self.last_proxy
        except:
            self.last_proxy = 0

        point = self.game_info.map_center.towards(
            self.enemy_start_locations[0], 20)

        if (self.structures(UnitTypeId.SUPPLYDEPOT).amount >= 1 and not self.proxy_built and self.can_afford(UnitTypeId.BARRACKS)) and (curent_iteration - self.last_sent) > 200:
            await self.build(UnitTypeId.BARRACKS, near=point)
            await self.chat_send("building proxy rax")
            self.proxy_built = True

        if(not self.structures(UnitTypeId.BARRACKS).closer_than(20, point).exists):
            self.proxy_built = False

    async def build_more_rax(self):
        if self.structures(UnitTypeId.SUPPLYDEPOT).exists:
            # Build up to 2 rax
            if (self.can_afford(UnitTypeId.BARRACKS) and self.structures(UnitTypeId.BARRACKS).amount + self.structures(UnitTypeId.BARRACKS).amount < 2):
                await self.build(UnitTypeId.BARRACKS, near=self.start_location)

    # on_step is a method that is called every step of the game.
    async def on_step(self, iteration: int):
        if iteration == 0:
            self.choose_tactic()
            # print(self.current_tactic)
            if self.current_tactic == 1:
                await self.chat_send("reaper rush")
            elif self.current_tactic == 2:
                await self.chat_send("proxy barracks")   
            await self.chat_send("(glhf)")
            
        # stops cannon rush to not use them forever    
        if iteration % 10000 == 0 and self.current_tactic == 4:
            self.current_tactic = self.current_tactic = random.randrange(1, 3)

        if not any(self.townhalls):
            # surrender
            await self.client.chat_send('(gg)', False)
            await self.client.leave()
            for unit in self.units:
                self.do_random_attack(unit)

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
        
        # marine micro
        marines = self.units(UnitTypeId.MARINE)
        enemy_location = self.enemy_start_locations[0]

        if self.structures(UnitTypeId.BARRACKS).ready and self.siege:
            rax = self.structures(UnitTypeId.BARRACKS).closest_to(enemy_location)
            for marine in marines:
                if marine.weapon_cooldown == 0:
                    marine.attack(enemy_location)
                elif marine.weapon_cooldown < 0:
                    marine.move(rax)
                else:
                    marine.move(rax)
                    
        # Reaper micro
        enemies: Units = self.enemy_units | self.enemy_structures
        enemies_can_attack: Units = enemies.filter(lambda unit: unit.can_attack_ground)
        for r in self.units(UnitTypeId.REAPER):

            # Move to range 15 of closest unit if reaper is below 20 hp and not regenerating
            enemy_threats_close: Units = enemies_can_attack.filter(
                lambda unit: unit.distance_to(r) < 15
            )  # Threats that can attack the reaper

            if r.health_percentage < 2 / 5 and enemy_threats_close:
                retreat_points: Set[Point2] = self.neighbors8(r.position,
                                                              distance=2) | self.neighbors8(r.position, distance=4)
                # Filter points that are pathable
                retreat_points: Set[Point2] = {x for x in retreat_points if self.in_pathing_grid(x)}
                if retreat_points:
                    closest_enemy: Unit = enemy_threats_close.closest_to(r)
                    retreat_point: Unit = closest_enemy.position.furthest(retreat_points)
                    r.move(retreat_point)
                    continue  # Continue for loop, dont execute any of the following

            # Reaper is ready to attack, shoot nearest ground unit
            enemy_ground_units: Units = enemies.filter(
                lambda unit: unit.distance_to(r) < 5 and not unit.is_flying
            )  # Hardcoded attackrange of 5
            if r.weapon_cooldown == 0 and enemy_ground_units:
                enemy_ground_units: Units = enemy_ground_units.sorted(lambda x: x.distance_to(r))
                closest_enemy: Unit = enemy_ground_units[0]
                r.attack(closest_enemy)
                continue  # Continue for loop, dont execute any of the following

            # Attack is on cooldown, check if grenade is on cooldown, if not then throw it to furthest enemy in range 5
            # pylint: disable=W0212
            reaper_grenade_range: float = (
                self.game_data.abilities[AbilityId.KD8CHARGE_KD8CHARGE.value]._proto.cast_range
            )
            enemy_ground_units_in_grenade_range: Units = enemies_can_attack.filter(
                lambda unit: not unit.is_structure and not unit.is_flying and unit.type_id not in
                {UnitTypeId.LARVA, UnitTypeId.EGG} and unit.distance_to(r) < reaper_grenade_range
            )
            if enemy_ground_units_in_grenade_range and (r.is_attacking or r.is_moving):
                # If AbilityId.KD8CHARGE_KD8CHARGE in abilities, we check that to see if the reaper grenade is off cooldown
                abilities = await self.get_available_abilities(r)
                enemy_ground_units_in_grenade_range = enemy_ground_units_in_grenade_range.sorted(
                    lambda x: x.distance_to(r), reverse=True
                )
                furthest_enemy: Unit = None
                for enemy in enemy_ground_units_in_grenade_range:
                    if await self.can_cast(r, AbilityId.KD8CHARGE_KD8CHARGE, enemy, cached_abilities_of_unit=abilities):
                        furthest_enemy: Unit = enemy
                        break
                if furthest_enemy:
                    r(AbilityId.KD8CHARGE_KD8CHARGE, furthest_enemy)
                    continue  # Continue for loop, don't execute any of the following

            # Move to max unit range if enemy is closer than 4
            enemy_threats_very_close: Units = enemies.filter(
                lambda unit: unit.can_attack_ground and unit.distance_to(r) < 4.5
            )  # Hardcoded attackrange minus 0.5
            # Threats that can attack the reaper
            if r.weapon_cooldown != 0 and enemy_threats_very_close:
                retreat_points: Set[Point2] = self.neighbors8(r.position,
                                                              distance=2) | self.neighbors8(r.position, distance=4)
                # Filter points that are pathable by a reaper
                retreat_points: Set[Point2] = {x for x in retreat_points if self.in_pathing_grid(x)}
                if retreat_points:
                    closest_enemy: Unit = enemy_threats_very_close.closest_to(r)
                    retreat_point: Point2 = max(
                        retreat_points, key=lambda x: x.distance_to(closest_enemy) - x.distance_to(r)
                    )
                    r.move(retreat_point)
                    continue  # Continue for loop, don't execute any of the following

            # Move to nearest enemy ground unit/building because no enemy unit is closer than 5
            all_enemy_ground_units: Units = self.enemy_units.not_flying
            if all_enemy_ground_units:
                closest_enemy: Unit = all_enemy_ground_units.closest_to(r)
                r.move(closest_enemy)
                continue  # Continue for loop, don't execute any of the following

            # Move to random enemy start location if no enemy buildings have been seen
            r.move(random.choice(self.enemy_start_locations))

        # Manage idle scvs, would be taken care by distribute workers aswell
        if self.townhalls:
            for w in self.workers.idle:
                th: Unit = self.townhalls.closest_to(w)
                mfs: Units = self.mineral_field.closer_than(10, th)
                if mfs:
                    mf: Unit = mfs.closest_to(w)
                    w.gather(mf)

        # Manage orbital energy and drop mules
        for oc in self.townhalls(UnitTypeId.ORBITALCOMMAND).filter(lambda x: x.energy >= 50):
            mfs: Units = self.mineral_field.closer_than(10, oc)
            if mfs:
                mf: Unit = max(mfs, key=lambda x: x.mineral_contents)
                oc(AbilityId.CALLDOWNMULE_CALLDOWNMULE, mf)
            
                    
        # scv defend itself            
        probe_targets = (self.enemy_units).closer_than(5, self.start_location)
        for unit in self.units(UnitTypeId.PROBE):
            if(probe_targets.amount > 3):
                target = probe_targets.closest_to(unit)
                unit.attack(target)            
                
        # Raise depos when enemies are nearby
        for depo in self.structures(UnitTypeId.SUPPLYDEPOT).ready:
            for unit in self.enemy_units:
                if unit.distance_to(depo) < 15:
                    break
            else:
                depo(AbilityId.MORPH_SUPPLYDEPOT_LOWER)

        # Lower depos when no enemies are nearby
        for depo in self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).ready:
            for unit in self.enemy_units:
                if unit.distance_to(depo) < 10:
                    depo(AbilityId.MORPH_SUPPLYDEPOT_RAISE)
                    break        
                
        # Build wall
        if self.can_afford(UnitTypeId.SUPPLYDEPOT) and self.already_pending(UnitTypeId.SUPPLYDEPOT) == 0:
            if len(depot_placement_positions) == 0:
                return
            # Choose any depot location
            target_depot_location: Point2 = depot_placement_positions.pop()
            workers: Units = self.workers.gathering
            if workers:  # if workers were found
                worker: Unit = workers.random
                worker.build(UnitTypeId.SUPPLYDEPOT, target_depot_location)

        # Build barracks
        if depots.ready and self.can_afford(UnitTypeId.BARRACKS) and self.already_pending(UnitTypeId.BARRACKS) == 0:
            if self.structures(UnitTypeId.BARRACKS).amount + self.already_pending(UnitTypeId.BARRACKS) > 0:
                return
            workers = self.workers.gathering
            if workers and barracks_placement_position:  # if workers were found
                worker: Unit = workers.random
                worker.build(UnitTypeId.BARRACKS, barracks_placement_position)        

        action = state_rwd_action['action']
        # await BotAction.take_action(action, iteration) this block might be moved
        '''
        0: expand (ie: move to next spot, or build to 16 (minerals)+3 assemblers+3)
    
        '''

        # 0: expand (ie: move to next spot, or build to 16 (minerals)+3 assemblers+3)
        if action == 0:
            try:
                await self.expand()
            except Exception as e:
                print(e)

        # 1: build base
        elif action == 1:
            try:
                if self.current_tactic == 1:
                    await self.build_more_rax()
            except Exception as e:
                print("Action 1", e)        
    
        # 2: build proxy rax
        elif action == 2:
            try:
                await self.build_proxy_rax(iteration)
            except Exception as e:
                print("Action 2", e)
                

        # 3: train units in rax
        elif action == 3:
            try:
                self.train_troop_in_building(
                    UnitTypeId.BARRACKS, UnitTypeId.MARRINE)
                self.train_troop_in_building(
                    UnitTypeId.BARRACKS, UnitTypeId.REAPER)
            except Exception as e:
                print("Action 3", e)
                
        # 4: build supply depots        
        elif action == 4:
            try:
                 if (
                    self.supply_left < 5 and self.townhalls and self.supply_used >= 14 and self.can_afford(UnitTypeId.SUPPLYDEPOT) and self.already_pending(UnitTypeId.SUPPLYDEPOT) < 1):
                        workers: Units = self.workers.gathering
                        # If workers were found
                        if workers:
                            worker: Unit = workers.furthest_to(workers.center)
                            location: Point2 = await self.find_placement(UnitTypeId.SUPPLYDEPOT, worker.position, placement_step=3)
                            # If a placement location was found
                            if location:
                                # Order worker to build exactly on that location
                                worker.build(UnitTypeId.SUPPLYDEPOT, location)      
            except Exception as e:
                print("Action 4", e)          

        # 5: send scout (evenly/random/closest to enemy?)
        elif action == 5:
            try:
                self.scout(curent_iteration=iteration)
            except Exception as e:
                print("Action 5", e)      

        # 6: defend attack try to use marine
        # TODO: more defensive tactics
        elif action == 6:
            try:
                # just attack it didn't work yet
                if self.enemy_units.exists:
                    targets = (self.enemy_units).filter(lambda unit: unit.can_be_attacked)
                    for unit in self.units(UnitTypeId.MARINE):
                        if(unit.is_idle):
                            target = targets.closest_to(unit)
                            if(target != None):
                                unit.attack(target)
                            else:     
                                self.do_random_attack(unit)
               
            except Exception as e:
                print("Action 6", e)

        # 7: attack base
        elif action == 7:
            try:
                for reaper in self.units(UnitTypeId.REAPER).ready.idle:
                    targets = (self.enemy_units | self.enemy_structures).filter(
                        lambda unit: unit.can_be_attacked)
                    if targets:
                        target = targets.closest_to(reaper)
                        reaper.attack(target)
                    else:
                        self.do_random_attack(reaper)     
                        
                # attack marine units, Make marrine attack either closest enemy unit or enemy spawn location        
                if self.units(UnitTypeId.MARINE).amount > 5:
                    self.siege = (self.enemy_structures).closer_than(25, self.enemy_start_locations[0]).exists
                    for marine in self.units(UnitTypeId.MARINE).ready.idle:
                        targets = (self.enemy_units | self.enemy_structures).filter(
                            lambda unit: unit.can_be_attacked)
                        if targets:
                            target = targets.closest_to(marine)
                            marine.attack(target)
                        else:
                            self.do_random_attack(marine)                                   

            except Exception as e:
                print("Action 9", e)

        # 8: unit flee
        # TODO: think about more complex algorythm for flee for eg. count chances to being attack
        elif action == 8:
            try:
                if self.units(UnitTypeId.MARINE).amount < 4:
                    self.flee_to_ramp(UnitTypeId.MARINE)
            except Exception as e:
                print("Action 8", e)

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

        #cv2.imshow('map', cv2.flip(cv2.resize(map, None, fx=4,
        #           fy=4, interpolation=cv2.INTER_NEAREST), 0))
        #cv2.waitKey(1)

        #if self.SAVE_REPLAY:
            # save map image into "replays dir"
            #cv2.imwrite(f"replays/{int(time.time())}-{iteration}.png", map)

        reward = 0

        try:
            attack_count = 0

            # iterate through our reapers:
            for reaper in self.units(UnitTypeId.REAPER):
                if reaper.is_attacking and reaper.target_in_range:
                    if self.enemy_units.closer_than(8, reaper) or self.enemy_structures.closer_than(8, reaper):
                        # reward += 0.005 # original was 0.005, decent results, but let's 3x it.
                        reward += 0.015
                        attack_count += 1

            # iterate through our marines:
            for marine in self.units(UnitTypeId.MARINE):
                if marine.is_attacking and marine.target_in_range:
                    if self.enemy_units.closer_than(8, marine) or self.enemy_structures.closer_than(8, marine):
                        # reward += 0.005 # original was 0.005, decent results, but let's 3x it.
                        reward += 0.01
                        attack_count += 1

             # iterate through our dark tanks:
            #for tank in self.units(UnitTypeId.SIEGETANK):
                # if voidray is attacking and is in range of enemy unit:
             #   if tank.is_attacking and tank.target_in_range:
              #      if self.enemy_units.closer_than(8, tank) or self.enemy_structures.closer_than(8, tank):
                        # reward += 0.005 # original was 0.005, decent results, but let's 3x it.
               #         reward += 0.015
                #        attack_count += 1 

        except Exception as e:
            print("reward", e)
            reward = 0

        if iteration % 100 == 0:
            print(
                f"Iter: {iteration}. RWD: {reward}. M: {self.units(UnitTypeId.MARINE).amount} T: {self.units(UnitTypeId.SIEGETANK).amount} R: {self.units(UnitTypeId.REAPER).amount}")

        save_map = np.resize(map, (160, 160, 3))

        # write the file:
        data = {"state": save_map, "reward": reward, "action": None,
                "done": False}  # empty action waiting for the next one!

        with open('data/state_rwd_action.pkl', 'wb') as f:
            pickle.dump(data, f)
