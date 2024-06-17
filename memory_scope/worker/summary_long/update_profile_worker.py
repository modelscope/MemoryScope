from typing import List

from common.response_text_parser import ResponseTextParser
from constants.common_constants import NEW_OBS_NODES, NEW_USER_PROFILE
from enumeration.memory_type_enum import MemoryTypeEnum
from model.memory_wrap_node import MemoryWrapNode
from model.user_attribute import UserAttribute
from worker.bailian.memory_base_worker import MemoryBaseWorker


class UpdateProfileWorker(MemoryBaseWorker):

    def filter_obs_nodes(self,
                         user_attr: UserAttribute,
                         new_obs_nodes: List[MemoryWrapNode]) -> (UserAttribute, List[MemoryWrapNode], float):
        max_score: float = 0
        filtered_nodes: List[MemoryWrapNode] = []
        result = self.rerank_client.call(query=user_attr.description,
                                         documents=[x.memory_node.content for x in new_obs_nodes])

        if not result:
            self.add_run_info(f"update_user_attr={user_attr.memory_key} call rerank failed!")
            return user_attr, filtered_nodes, max_score

        # 找到大于阈值的obs node
        filtered_nodes: List[MemoryWrapNode] = []
        for rank_node in result:
            index = rank_node["index"]
            score = rank_node["relevance_score"]
            node = new_obs_nodes[index]
            keep_flag = "filtered"
            if score >= self.config.update_profile_threshold:
                filtered_nodes.append(node)
                keep_flag = "keep"
                max_score = max(max_score, score)
            self.logger.info(f"key={user_attr.memory_key} desc={user_attr.description} "
                             f"content={node.memory_node.content} score={score} keep_flag={keep_flag}")

        if not filtered_nodes:
            self.logger.info(f"update_user_attr={user_attr} filtered_nodes is empty!")
        return user_attr, filtered_nodes, max_score

    def update_user_attr(self, user_attr: UserAttribute, filtered_nodes: List[MemoryWrapNode]) -> UserAttribute:
        self.logger.info(f"update_user_attr memory_key={user_attr.memory_key} desc={user_attr.description} "
                         f"value={user_attr.value} doc.size={len(filtered_nodes)}")

        # 根据不同的参数类型是否多值，分别给出prompt
        user_query_list = []
        for node in filtered_nodes:
            user_query_list.append(f"句子：{node.memory_node.content}")
        update_profile = f"{user_attr.memory_key}（{user_attr.description}）"
        update_profile_value = update_profile + "：" + "，".join(user_attr.value)

        if user_attr.is_unique == 1:
            update_profile_message = self.prompt_to_msg(
                system_prompt=self.prompt_config.update_unique_profile_system,
                few_shot=self.prompt_config.update_unique_profile_few_shot,
                user_query=self.prompt_config.update_unique_profile_user_query.format(
                    user_query="\n".join(user_query_list),
                    update_profile=update_profile,
                    update_profile_value=update_profile_value))
        else:
            update_profile_message = self.prompt_to_msg(
                system_prompt=self.prompt_config.update_plural_profile_system,
                few_shot=self.prompt_config.update_plural_profile_few_shot,
                user_query=self.prompt_config.update_plural_profile_user_query.format(
                    user_query="\n".join(user_query_list),
                    update_profile=update_profile,
                    update_profile_value=update_profile_value))
        self.logger.info(f"update_profile_message={update_profile_message}")

        # call LLM
        response_text: str = self.gene_client.call(messages=update_profile_message,
                                                   model_name=self.config.update_profile_model,
                                                   max_token=self.config.update_profile_max_token,
                                                   temperature=self.config.update_profile_temperature,
                                                   top_k=self.config.update_profile_top_k)

        # return if empty
        if not response_text:
            self.add_run_info(f"update_one_user_attr key={user_attr.memory_key} call llm failed!")
            return user_attr

        profile_list = ResponseTextParser(response_text).parse_v1(f"update_attr {user_attr.memory_key}")
        if not profile_list:
            self.add_run_info(f"update_one_user_attr key={user_attr.memory_key} profile_list empty 1!")
            return user_attr
        profile_list = profile_list[0]
        if not profile_list:
            self.add_run_info(f"update_one_user_attr key={user_attr.memory_key} profile_list empty 2")
            return user_attr
        profile = profile_list[0]

        if not profile or profile in ["无", "重复"]:
            self.logger.info(f"profile={profile}, skip.")
            return user_attr

        # check 英文中午逗号
        if user_attr.is_unique == 1:
            user_attr.value = [profile.strip()]
        else:
            attr_value_list = profile.replace("，", ",").split(",")
            user_attr.value = [x.strip() for x in sorted(list(set(user_attr.value + attr_value_list)))]
        return user_attr

    def add_extra_user_attrs(self):
        # 解析为空返回
        extra_user_attr_list = [x.strip() for x in self.config.extra_user_attrs if x.strip()]
        if not extra_user_attr_list:
            return

        for user_attr_info in extra_user_attr_list:
            user_attr_split = user_attr_info.split(":")

            # 格式不对返回
            if len(user_attr_split) < 1:
                continue
            user_attr_key = user_attr_split[0]

            user_attr_desc = ""
            if len(user_attr_split) >= 2:
                user_attr_desc = user_attr_split[1]

            user_attr_unique = 0
            if len(user_attr_split) >= 3:
                user_attr_unique = int(user_attr_split[2])

            # 已经包含返回
            if user_attr_key in self.user_profile_dict:
                user_attr = self.user_profile_dict[user_attr_key]
                # description为空，补充description
                if not user_attr.description:
                    user_attr.description = user_attr_desc
                continue

            # 增加新属性
            new_attr = UserAttribute(memory_id=self.config.memory_id,
                                     scene=self.scene,
                                     memory_key=user_attr_key,
                                     is_unique=int(user_attr_unique),
                                     is_mutable=1,
                                     memory_type=MemoryTypeEnum.PROFILE,
                                     description=user_attr_desc,
                                     status=1)
            self.user_profile_dict[user_attr_key] = new_attr

    def _run(self):
        new_obs_nodes: List[MemoryWrapNode] = self.get_context(NEW_OBS_NODES)
        if not new_obs_nodes:
            self.logger.info("new_obs_nodes is empty, stop user profile!")
            self.set_context(NEW_USER_PROFILE, list(self.user_profile_dict.values()))
            return

        # 增加环境变量配置的属性
        if self.config.extra_user_attrs:
            self.add_extra_user_attrs()

        new_user_profile: List[UserAttribute] = []
        self.set_context(NEW_USER_PROFILE, new_user_profile)

        for user_attr_key, user_attr in self.user_profile_dict.items():
            # 不可修改直接跳过
            if user_attr.is_mutable != 1:
                new_user_profile.append(user_attr)
                self.logger.info(f"{user_attr_key} is not mutable! continue")
                continue

            self.submit_thread(self.filter_obs_nodes,
                               sleep_time=0.1,
                               user_attr=user_attr,
                               new_obs_nodes=new_obs_nodes)

        # 选择topN
        result_list = []
        for result in self.join_threads():
            user_attr, filtered_nodes, max_score = result
            if not filtered_nodes:
                continue
            result_list.append(result)
        result_sorted = sorted(result_list, key=lambda x: x[2], reverse=True)
        if len(result_sorted) > self.config.update_profile_max_thread:
            result_sorted = result_sorted[:self.config.update_profile_max_thread]

        # 提交LLM update任务
        for user_attr, filtered_nodes, _ in result_sorted:
            self.submit_thread(self.update_user_attr,
                               sleep_time=1,
                               user_attr=user_attr,
                               filtered_nodes=filtered_nodes)

        # collect result & save
        for result in self.join_threads():
            if result:
                user_attribute: UserAttribute = result
                self.logger.info(f"after_update_profile memory_key={user_attribute.memory_key} "
                                 f"desc={user_attribute.description} value={user_attribute.value}")
                new_user_profile.append(user_attribute)
