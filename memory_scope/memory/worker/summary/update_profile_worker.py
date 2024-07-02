from typing import List

from memory_scope.utils.response_text_parser import ResponseTextParser
from memory_scope.constants.common_constants import NEW_OBS_NODES, NEW_USER_PROFILE
from memory_scope.enumeration.memory_type_enum import MemoryTypeEnum
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.utils.global_context import GlobalContext
from memory_scope.utils.tool_functions import prompt_to_msg
from memory_scope.constants.language_constants import COMMA_WORD, COLON_WORD


class UpdateProfileWorker(MemoryBaseWorker):
    @property
    def extra_user_attrs(self):
        return GlobalContext.global_configs.get("extra_user_attrs", [])

    def filter_obs_nodes(
        self, user_attr: MemoryNode, new_obs_nodes: List[MemoryNode]
    ) -> (MemoryNode, List[MemoryNode], float):
        max_score: float = 0
        filtered_nodes: List[MemoryNode] = []
        result = self.rank_model.call(
            query=user_attr.meta_data.get("description", ""),
            documents=[x.content for x in new_obs_nodes],
        )

        if not result:
            self.add_run_info(
                f"update_user_attr={user_attr.meta_data.get("memory_key", "")} call rerank failed!"
            )
            return user_attr, filtered_nodes, max_score

        # 找到大于阈值的obs node
        filtered_nodes: List[MemoryNode] = []
        for index, score in result.rank_scores.items():
            node = new_obs_nodes[index]
            keep_flag = "filtered"
            if score >= self.update_profile_threshold:
                filtered_nodes.append(node)
                keep_flag = "keep"
                max_score = max(max_score, score)
            self.logger.info(
                f"key={user_attr.meta_data.get("memory_key", "")} desc={user_attr.meta_data.get("description", "")} "
                f"content={node.content} score={score} keep_flag={keep_flag}"
            )

        if not filtered_nodes:
            self.logger.info(f"update_user_attr={user_attr} filtered_nodes is empty!")
        return user_attr, filtered_nodes, max_score

    def update_user_attr(
        self, user_attr: MemoryNode, filtered_nodes: List[MemoryNode]
    ) -> MemoryNode:
        self.logger.info(
            f"update_user_attr memory_key={user_attr.meta_data.get("memory_key", "")} desc={user_attr.meta_data.get("description", "")} "
            f"value={user_attr.meta_data.get("value", "")} doc.size={len(filtered_nodes)}"
        )

        # 根据不同的参数类型是否多值，分别给出prompt
        user_query_list = []
        for node in filtered_nodes:
            user_query_list.append(self.prompt_handler.user_query.format(content=node.content))
        update_profile = f"{user_attr.meta_data.get("memory_key", "")}({user_attr.meta_data.get("description", "")})"
        update_profile_value = update_profile + self.get_language_prompt(COLON_WORD) + self.get_language_prompt(COMMA_WORD).join(user_attr.meta_data.get("value", ""))

        if user_attr.meta_data.get("is_unique", 0) == 1:
            update_profile_message = prompt_to_msg(
                system_prompt=self.prompt_handler.update_unique_profile_system_prompt,
                few_shot=self.prompt_handler.update_unique_profile_few_shot_prompt,
                user_query=self.prompt_handler.update_unique_profile_user_query_prompt.format(
                    user_query="\n".join(user_query_list),
                    update_profile=update_profile,
                    update_profile_value=update_profile_value,
                ),
            )
        else:
            update_profile_message = prompt_to_msg(
                system_prompt=self.prompt_handler.update_plural_profile_system_prompt,
                few_shot=self.prompt_handler.update_plural_profile_few_shot_prompt,
                user_query=self.prompt_handler.update_plural_profile_user_query_prompt.format(
                    user_query="\n".join(user_query_list),
                    update_profile=update_profile,
                    update_profile_value=update_profile_value,
                ),
            )
        self.logger.info(f"update_profile_message={update_profile_message}")

        # call LLM
        response: str = self.generation_model.call(
            messages=update_profile_message,
            model_name=self.update_profile_model,
            max_token=self.update_profile_max_token,
            temperature=self.update_profile_temperature,
            top_k=self.update_profile_top_k,
        )

        # return if empty
        if not response:
            self.add_run_info(
                f"update_one_user_attr key={user_attr.meta_data.get("memory_key", "")} call llm failed!"
            )
            return user_attr

        profile_list = ResponseTextParser(response.message.content).parse_v1(
            f"update_attr {user_attr.meta_data.get("memory_key", "")}"
        )
        if not profile_list:
            self.add_run_info(
                f"update_one_user_attr key={user_attr.meta_data.get("memory_key", "")} profile_list empty 1!"
            )
            return user_attr
        profile_list = profile_list[0]
        if not profile_list:
            self.add_run_info(
                f"update_one_user_attr key={user_attr.meta_data.get("memory_key", "")} profile_list empty 2"
            )
            return user_attr
        profile = profile_list[0]

        if not profile or profile in self.prompt_handler.update_profile_key:
            self.logger.info(f"profile={profile}, skip.")
            return user_attr

        # check 英文中午逗号
        if user_attr.meta_data.get("is_unique", 0) == 1:
            user_attr.meta_data["value"] = [profile.strip()]
        else:
            attr_value_list = profile.replace("，", ",").split(",")
            user_attr.meta_data["value"] = [
                x.strip() for x in sorted(list(set(user_attr.meta_data.get("value", "") + attr_value_list)))
            ]
        return user_attr

    def add_extra_user_attrs(self):
        # 解析为空返回
        extra_user_attr_list = [x.strip() for x in self.extra_user_attrs if x.strip()]
        if not extra_user_attr_list:
            return

        for user_attr_info in extra_user_attr_list:
            user_attr_split = user_attr_info.split(self.get_language_prompt(COLON_WORD))

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
                if not user_attr.meta_data.get("description", ""):
                    user_attr.meta_data["description"] = user_attr_desc
                continue

            # 增加新属性
            new_attr = MemoryNode(
                memory_id=self.memory_id,
                meta_data={
                    "memory_key": user_attr_key,
                    "is_unique": int(user_attr_unique),
                    "is_mutable": 1,
                    "description": user_attr_desc
                },
                memory_type=MemoryTypeEnum.PROFILE,
                status=1,
                obs_profile_updated=true,
            )
            self.user_profile_dict[user_attr_key] = new_attr

    def _run(self):
        new_obs_nodes: List[MemoryNode] = self.get_context(NEW_OBS_NODES)
        if not new_obs_nodes:
            self.logger.info("new_obs_nodes is empty, stop user profile!")
            self.set_context(NEW_USER_PROFILE, list(self.user_profile_dict.values()))
            return

        # 增加环境变量配置的属性
        if self.extra_user_attrs:
            self.add_extra_user_attrs()

        new_user_profile: List[MemoryNode] = []
        self.set_context(NEW_USER_PROFILE, new_user_profile)

        for user_attr_key, user_attr in self.user_profile_dict.items():
            # 不可修改直接跳过
            if user_attr.meta_data.get("is_mutable", 0) != 1:
                new_user_profile.append(user_attr)
                self.logger.info(f"{user_attr_key} is not mutable! continue")
                continue

            self.submit_thread(
                self.filter_obs_nodes,
                sleep_time=0.1,
                user_attr=user_attr,
                new_obs_nodes=new_obs_nodes,
            )

        # 选择topN
        result_list = []
        for result in self.join_threads():
            user_attr, filtered_nodes, max_score = result
            if not filtered_nodes:
                continue
            result_list.append(result)
        result_sorted = sorted(result_list, key=lambda x: x[2], reverse=True)
        if len(result_sorted) > self.update_profile_max_thread:
            result_sorted = result_sorted[: self.update_profile_max_thread]

        # 提交LLM update任务
        for user_attr, filtered_nodes, _ in result_sorted:
            self.submit_thread(
                self.update_user_attr,
                sleep_time=1,
                user_attr=user_attr,
                filtered_nodes=filtered_nodes,
            )

        # collect result & save
        for result in self.join_threads():
            if result:
                user_attribute: MemoryNode = result
                self.logger.info(
                    f"after_update_profile memory_key={user_attribute.meta_data.get("memory_key", "")} "
                    f"desc={user_attribute.meta_data.get("description", "")} value={user_attribute.meta_data.get("value", "")}"
                )
                new_user_profile.append(user_attribute)
