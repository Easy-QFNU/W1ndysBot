from .. import (
    MODULE_NAME,
    SWITCH_NAME,
    SIGN_IN_COMMAND,
    SELECT_COMMAND,
    QUERY_COMMAND,
    RANKING_COMMAND,
    LOTTERY_COMMAND,
    LOTTERY_COST,
    LOTTERY_REWARD_MIN,
    LOTTERY_REWARD_MAX,
    SPEECH_REWARD_MIN,
    SPEECH_REWARD_MAX,
    MILESTONE_VALUES,
    MILESTONE_NOTIFY_INTERVAL,
    ANNOUNCEMENT_MESSAGE,
)
from core.menu_manager import MENU_COMMAND
import logger
from core.switchs import is_group_switch_on, handle_module_group_switch
from utils.auth import is_system_admin
from api.message import send_group_msg
from utils.generate import generate_text_message, generate_reply_message
from datetime import datetime
from .database.data_manager import DataManager
from core.menu_manager import MenuManager
import random


class GroupMessageHandler:
    """群消息处理器"""

    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.time = msg.get("time", "")
        self.formatted_time = datetime.fromtimestamp(self.time).strftime(
            "%Y-%m-%d %H:%M:%S"
        )  # 格式化时间
        self.sub_type = msg.get("sub_type", "")  # 子类型，只有normal
        self.group_id = str(msg.get("group_id", ""))  # 群号
        self.message_id = str(msg.get("message_id", ""))  # 消息ID
        self.user_id = str(msg.get("user_id", ""))  # 发送者QQ号
        self.message = msg.get("message", {})  # 消息段数组
        self.raw_message = msg.get("raw_message", "")  # 原始消息
        self.sender = msg.get("sender", {})  # 发送者信息
        self.nickname = self.sender.get("nickname", "")  # 昵称
        self.card = self.sender.get("card", "")  # 群名片
        self.role = self.sender.get("role", "")  # 群身份

    async def _handle_switch_command(self):
        """
        处理群聊开关命令
        """
        if self.raw_message.lower() == SWITCH_NAME.lower():
            # 鉴权
            if not is_system_admin(self.user_id):
                logger.error(f"[{MODULE_NAME}]{self.user_id}无权限切换群聊开关")
                return True
            await handle_module_group_switch(
                MODULE_NAME,
                self.websocket,
                self.group_id,
                self.message_id,
            )
            return True
        return False

    async def _handle_menu_command(self):
        """
        处理菜单命令（无视开关状态）
        """
        if self.raw_message.lower() == f"{SWITCH_NAME}{MENU_COMMAND}".lower():
            menu_text = MenuManager.get_module_commands_text(MODULE_NAME)
            await send_group_msg(
                self.websocket,
                self.group_id,
                [
                    generate_reply_message(self.message_id),
                    generate_text_message(menu_text),
                ],
                note="del_msg=30",
            )
            return True
        return False

    async def _handle_sign_in_command(self):
        """
        处理签到命令
        """
        try:
            if self.raw_message.startswith(SIGN_IN_COMMAND):
                with DataManager() as dm:
                    # 首先检查用户是否已经选择了类型
                    user_info = dm.get_user_info(self.group_id, self.user_id)

                    if user_info["code"] != 200 or not user_info["data"]:
                        # 用户没有选择类型
                        no_selection_message = (
                            "❌ 您还没有选择类型！\n"
                            "🌟 请先选择您的类型：\n"
                            "✨ 阳光类型：发送「选择 阳光」\n"
                            "💧 雨露类型：发送「选择 雨露」\n"
                            "📝 选择后即可开始签到获得奖励！"
                        )
                        await send_group_msg(
                            self.websocket,
                            self.group_id,
                            [
                                generate_reply_message(self.message_id),
                                generate_text_message(no_selection_message),
                                generate_text_message(ANNOUNCEMENT_MESSAGE),
                            ],
                            note="del_msg=10",
                        )
                        return

                    # 获取用户的类型（可能有多个，取第一个）
                    user_type = user_info["data"][0][3]  # type字段

                    # 执行签到
                    result = dm.daily_checkin(self.group_id, self.user_id, user_type)
                    await send_group_msg(
                        self.websocket,
                        self.group_id,
                        [
                            generate_reply_message(self.message_id),
                            generate_text_message(result["message"]),
                            generate_text_message(ANNOUNCEMENT_MESSAGE),
                        ],
                        note="del_msg=10",
                    )
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理签到命令失败: {e}")

    async def _handle_select_command(self):
        """
        处理选择命令
        """
        try:
            if self.raw_message.startswith(SELECT_COMMAND):
                # 解析用户选择的类型
                message_parts = self.raw_message.strip().split()

                if len(message_parts) < 2:
                    # 用户只输入了"选择"，提供帮助信息
                    help_message = (
                        "🌟 请选择您的类型：\n"
                        "✨ 阳光类型：发送「选择 阳光」\n"
                        "💧 雨露类型：发送「选择 雨露」\n"
                        "📝 选择后即可开始签到获得奖励！"
                    )
                    await send_group_msg(
                        self.websocket,
                        self.group_id,
                        [
                            generate_reply_message(self.message_id),
                            generate_text_message(help_message),
                            generate_text_message(ANNOUNCEMENT_MESSAGE),
                        ],
                        note="del_msg=10",
                    )
                    return

                choice = message_parts[1].strip()
                user_type = None

                if choice in ["阳光", "阳光类型", "阳光型", "sun", "sunshine"]:
                    user_type = 0
                elif choice in [
                    "雨露",
                    "雨露",
                    "雨露类型",
                    "雨露类型",
                    "rain",
                    "raindrop",
                ]:
                    user_type = 1
                else:
                    # 无效选择
                    error_message = (
                        "❌ 选择无效！\n"
                        "🌟 请选择以下类型之一：\n"
                        "✨ 阳光类型：发送「选择 阳光」\n"
                        "💧 雨露类型：发送「选择 雨露」\n"
                        "📝 提示：输入格式为「选择 类型名称」"
                    )
                    await send_group_msg(
                        self.websocket,
                        self.group_id,
                        [
                            generate_reply_message(self.message_id),
                            generate_text_message(error_message),
                            generate_text_message(ANNOUNCEMENT_MESSAGE),
                        ],
                        note="del_msg=10",
                    )
                    return

                # 添加用户
                with DataManager() as dm:
                    result = dm.add_user(self.group_id, self.user_id, user_type)
                    await send_group_msg(
                        self.websocket,
                        self.group_id,
                        [
                            generate_reply_message(self.message_id),
                            generate_text_message(result["message"]),
                            generate_text_message(ANNOUNCEMENT_MESSAGE),
                        ],
                        note="del_msg=10",
                    )
                    return
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理选择命令失败: {e}")

    async def _handle_query_command(self):
        """
        处理查询命令 - 查看用户当前拥有的数值
        """
        try:
            if self.raw_message.startswith(QUERY_COMMAND):
                with DataManager() as dm:
                    # 检查用户是否已经选择了类型
                    user_info = dm.get_user_info(self.group_id, self.user_id)

                    if user_info["code"] != 200 or not user_info["data"]:
                        # 用户还没有选择类型
                        no_selection_message = (
                            "❌ 您还没有选择类型！\n"
                            "🌟 请先选择您的类型：\n"
                            "✨ 阳光类型：发送「选择 阳光」\n"
                            "💧 雨露类型：发送「选择 雨露」\n"
                            "📝 选择后即可开始签到和获得发言奖励！"
                        )
                        await send_group_msg(
                            self.websocket,
                            self.group_id,
                            [
                                generate_reply_message(self.message_id),
                                generate_text_message(no_selection_message),
                                generate_text_message(ANNOUNCEMENT_MESSAGE),
                            ],
                            note="del_msg=10",
                        )
                        return

                    # 获取用户信息
                    user_data = user_info["data"][0]
                    user_type = user_data[3]  # type字段
                    type_name = "阳光" if user_type == 0 else "雨露"
                    count = user_data[4]  # count字段
                    consecutive_days = user_data[5]  # consecutive_days字段
                    total_checkin_days = user_data[7]  # total_checkin_days字段
                    last_checkin_date = user_data[6]  # last_checkin_date字段

                    # 构建查询结果消息
                    query_message = (
                        f"📊 您的{type_name}状态\n"
                        f"💎 当前拥有：{count}个{type_name}\n"
                        f"📈 连续签到：{consecutive_days}天\n"
                        f"📅 累计签到：{total_checkin_days}天\n"
                    )

                    if last_checkin_date:
                        query_message += f"⏰ 上次签到：{last_checkin_date}\n"

                    # 添加鼓励信息
                    if count >= 1000:
                        query_message += "🏆 您已经是超级大佬了！"
                    elif count >= 500:
                        query_message += "🌟 您的努力真是令人敬佩！"
                    elif count >= 200:
                        query_message += "✨ 继续加油，您很棒！"
                    elif count >= 100:
                        query_message += "🎯 已经突破100了，真不错！"
                    elif count >= 50:
                        query_message += "💪 半百达成，继续努力！"
                    else:
                        query_message += "📝 多发言多签到，数值会越来越多哦！"

                    await send_group_msg(
                        self.websocket,
                        self.group_id,
                        [
                            generate_reply_message(self.message_id),
                            generate_text_message(query_message),
                            generate_text_message(ANNOUNCEMENT_MESSAGE),
                        ],
                        note="del_msg=10",
                    )
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理查询命令失败: {e}")

    async def _handle_ranking_command(self):
        """
        处理排行榜命令 - 查看全服前十名或本群前十名
        只支持完全匹配和带指定参数的格式
        """
        try:
            message_parts = self.raw_message.strip().split()

            # 只处理完全匹配的情况
            if len(message_parts) == 1 and message_parts[0] == RANKING_COMMAND:
                # 完全匹配"排行榜"，显示所有类型
                show_type = None
                type_name = "全部"
            elif len(message_parts) == 2 and message_parts[0] == RANKING_COMMAND:
                # 带参数的格式"排行榜 类型"
                choice = message_parts[1].strip()
                if choice in ["阳光", "阳光类型", "阳光型", "sun", "sunshine"]:
                    show_type = 0
                    type_name = "阳光"
                elif choice in ["雨露", "雨露类型", "雨露型", "rain", "raindrop"]:
                    show_type = 1
                    type_name = "雨露"
                else:
                    # 不识别的类型，静默处理
                    return
            else:
                # 不符合格式，静默处理
                return

                with DataManager() as dm:
                    ranking_message = f"📊 {type_name}排行榜\n\n"

                    # 根据是否指定类型决定显示方式
                    if show_type is not None:
                        # 显示指定类型的排行榜
                        # 全服前十
                        global_result = dm.get_global_ranking(show_type, 10)
                        if global_result["code"] == 200 and global_result["data"]:
                            ranking_message += f"🌍 全服{type_name}前十名：\n"
                            for i, (user_id, group_id, count) in enumerate(
                                global_result["data"], 1
                            ):
                                ranking_message += (
                                    f"{i}. {user_id} - {count}个{type_name}\n"
                                )
                        else:
                            ranking_message += f"🌍 全服{type_name}榜：暂无数据\n"

                        ranking_message += "\n"

                        # 本群前十
                        group_result = dm.get_group_ranking(
                            self.group_id, show_type, 10
                        )
                        if group_result["code"] == 200 and group_result["data"]:
                            ranking_message += f"👥 本群{type_name}前十名：\n"
                            for i, (user_id, count) in enumerate(
                                group_result["data"], 1
                            ):
                                ranking_message += (
                                    f"{i}. {user_id} - {count}个{type_name}\n"
                                )
                        else:
                            ranking_message += f"👥 本群{type_name}榜：暂无数据\n"
                    else:
                        # 显示所有类型的排行榜
                        for type_val, type_str in [(0, "阳光"), (1, "雨露")]:
                            # 全服前五
                            global_result = dm.get_global_ranking(type_val, 5)
                            if global_result["code"] == 200 and global_result["data"]:
                                ranking_message += f"🌍 全服{type_str}前五名：\n"
                                for i, (user_id, group_id, count) in enumerate(
                                    global_result["data"], 1
                                ):
                                    ranking_message += (
                                        f"{i}. {user_id} - {count}个{type_str}\n"
                                    )
                            else:
                                ranking_message += f"🌍 全服{type_str}榜：暂无数据\n"

                            ranking_message += "\n"

                            # 本群前五
                            group_result = dm.get_group_ranking(
                                self.group_id, type_val, 5
                            )
                            if group_result["code"] == 200 and group_result["data"]:
                                ranking_message += f"👥 本群{type_str}前五名：\n"
                                for i, (user_id, count) in enumerate(
                                    group_result["data"], 1
                                ):
                                    ranking_message += (
                                        f"{i}. {user_id} - {count}个{type_str}\n"
                                    )
                            else:
                                ranking_message += f"👥 本群{type_str}榜：暂无数据\n"

                            ranking_message += "\n"

                    ranking_message += "💡 提示：发送「排行榜 阳光」或「排行榜 雨露」查看指定类型详细排行"

                    await send_group_msg(
                        self.websocket,
                        self.group_id,
                        [
                            generate_reply_message(self.message_id),
                            generate_text_message(ranking_message),
                            generate_text_message(ANNOUNCEMENT_MESSAGE),
                        ],
                        note="del_msg=30",
                    )
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理排行榜命令失败: {e}")

    async def _handle_lottery_command(self):
        """
        处理抽奖命令 - 抽阳光/抽雨露
        """
        try:
            if self.raw_message.startswith(LOTTERY_COMMAND):
                message_parts = self.raw_message.strip()

                # 解析抽奖类型
                lottery_type = None
                type_name = ""

                if message_parts in [
                    f"{LOTTERY_COMMAND}阳光",
                    f"{LOTTERY_COMMAND}太阳",
                ]:
                    lottery_type = 0
                    type_name = "阳光"
                elif message_parts in [
                    f"{LOTTERY_COMMAND}雨露",
                    f"{LOTTERY_COMMAND}雨",
                ]:
                    lottery_type = 1
                    type_name = "雨露"
                else:
                    # 不符合格式，静默处理
                    return

                with DataManager() as dm:
                    # 首先检查用户是否已经选择了类型
                    user_info = dm.get_user_info(self.group_id, self.user_id)

                    if user_info["code"] != 200 or not user_info["data"]:
                        # 用户还没有选择类型
                        no_selection_message = (
                            "❌ 您还没有选择类型！\n"
                            "🌟 请先选择您的类型：\n"
                            "✨ 阳光类型：发送「选择 阳光」\n"
                            "💧 雨露类型：发送「选择 雨露」\n"
                            "📝 选择后即可开始抽奖！"
                        )
                        await send_group_msg(
                            self.websocket,
                            self.group_id,
                            [
                                generate_reply_message(self.message_id),
                                generate_text_message(no_selection_message),
                                generate_text_message(ANNOUNCEMENT_MESSAGE),
                            ],
                            note="del_msg=10",
                        )
                        return

                    # 获取用户的类型
                    user_data = user_info["data"][0]
                    user_type = user_data[3]  # type字段
                    user_type_name = "阳光" if user_type == 0 else "雨露"
                    current_count = user_data[4]  # count字段

                    # 检查用户类型是否匹配
                    if user_type != lottery_type:
                        mismatch_message = (
                            f"❌ 类型不匹配！\n"
                            f"📝 您的类型是：{user_type_name}\n"
                            f"🎲 只能使用「抽{user_type_name}」命令\n"
                            f"💡 提示：每个用户只能抽取自己类型的奖励"
                        )
                        await send_group_msg(
                            self.websocket,
                            self.group_id,
                            [
                                generate_reply_message(self.message_id),
                                generate_text_message(mismatch_message),
                                generate_text_message(ANNOUNCEMENT_MESSAGE),
                            ],
                            note="del_msg=10",
                        )
                        return

                    # 检查用户是否有足够的数值
                    if current_count < LOTTERY_COST:
                        insufficient_message = (
                            f"❌ {type_name}不足！\n"
                            f"💎 当前拥有：{current_count}个{type_name}\n"
                            f"🎲 抽奖需要：{LOTTERY_COST}个{type_name}\n"
                            f"📝 请通过签到和发言获得更多{type_name}"
                        )
                        await send_group_msg(
                            self.websocket,
                            self.group_id,
                            [
                                generate_reply_message(self.message_id),
                                generate_text_message(insufficient_message),
                                generate_text_message(ANNOUNCEMENT_MESSAGE),
                            ],
                            note="del_msg=10",
                        )
                        return

                    # 执行抽奖：先扣除花费，再给予奖励
                    # 扣除花费
                    cost_result = dm.update_user_count(
                        self.group_id, self.user_id, user_type, -LOTTERY_COST
                    )

                    if cost_result["code"] != 200:
                        error_message = f"❌ 抽奖失败：{cost_result['message']}"
                        await send_group_msg(
                            self.websocket,
                            self.group_id,
                            [
                                generate_reply_message(self.message_id),
                                generate_text_message(error_message),
                                generate_text_message(ANNOUNCEMENT_MESSAGE),
                            ],
                            note="del_msg=10",
                        )
                        return

                    # 随机奖励
                    reward_amount = random.randint(
                        LOTTERY_REWARD_MIN, LOTTERY_REWARD_MAX
                    )

                    # 给予奖励
                    reward_result = dm.update_user_count(
                        self.group_id, self.user_id, user_type, reward_amount
                    )

                    if reward_result["code"] != 200:
                        # 如果给予奖励失败，需要把花费退回去
                        dm.update_user_count(
                            self.group_id, self.user_id, user_type, LOTTERY_COST
                        )
                        error_message = f"❌ 抽奖失败：{reward_result['message']}"
                        await send_group_msg(
                            self.websocket,
                            self.group_id,
                            [
                                generate_reply_message(self.message_id),
                                generate_text_message(error_message),
                                generate_text_message(ANNOUNCEMENT_MESSAGE),
                            ],
                            note="del_msg=10",
                        )
                        return

                    final_count = reward_result["data"]["count"]
                    net_change = reward_amount - LOTTERY_COST

                    # 构建抽奖结果消息
                    lottery_message = (
                        f"🎲 抽{type_name}结果\n"
                        f"💰 花费：{LOTTERY_COST}个{type_name}\n"
                        f"🎁 获得：{reward_amount}个{type_name}\n"
                        f"📊 净收益：{net_change:+}个{type_name}\n"
                        f"💎 当前拥有：{final_count}个{type_name}"
                    )

                    # 添加结果评价
                    if reward_amount >= 15:
                        lottery_message += "\n🎉 大奖！运气爆棚！"
                    elif reward_amount >= 10:
                        lottery_message += "\n✨ 不错的运气！"
                    elif reward_amount >= 5:
                        lottery_message += "\n😊 运气还行！"
                    else:
                        lottery_message += "\n😅 下次会更好的！"

                    await send_group_msg(
                        self.websocket,
                        self.group_id,
                        [
                            generate_reply_message(self.message_id),
                            generate_text_message(lottery_message),
                            generate_text_message(ANNOUNCEMENT_MESSAGE),
                        ],
                        note="del_msg=10",
                    )

        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理抽奖命令失败: {e}")

    async def _handle_speech_reward(self):
        """
        处理发言奖励 - 用户每次发言随机获得1-5个数值
        """
        try:
            with DataManager() as dm:
                # 检查用户是否已经选择了类型
                user_info = dm.get_user_info(self.group_id, self.user_id)

                if user_info["code"] != 200 or not user_info["data"]:
                    # 用户还没有选择类型，不给予奖励
                    return

                # 获取用户的类型
                user_type = user_info["data"][0][3]  # type字段
                type_name = "阳光" if user_type == 0 else "雨露"

                # 随机生成1-5的奖励
                reward_amount = random.randint(SPEECH_REWARD_MIN, SPEECH_REWARD_MAX)

                # 更新用户数值
                update_result = dm.update_user_count(
                    self.group_id, self.user_id, user_type, reward_amount
                )

                if update_result["code"] == 200:
                    logger.info(
                        f"[{MODULE_NAME}]发言奖励，user_id:{self.user_id},group_id:{self.group_id},user_type:{user_type},reward_amount:{reward_amount},new_count:{update_result['data']['count']}"
                    )
                    new_count = update_result["data"]["count"]

                    # 发送奖励提示消息（低频率，避免刷屏）
                    # 只有在特殊情况下才提示
                    should_notify = (
                        reward_amount == SPEECH_REWARD_MAX  # 获得最高奖励5时提示
                        or new_count % MILESTONE_NOTIFY_INTERVAL
                        == 0  # 每100个数值时提示
                        or new_count in MILESTONE_VALUES  # 特定里程碑提示
                    )

                    if should_notify:
                        reward_message = (
                            f"🎉 发言奖励！\n"
                            f"💎 获得：{reward_amount}个{type_name}\n"
                            f"📊 当前拥有：{new_count}个{type_name}"
                        )

                        # 添加里程碑特殊提示
                        if new_count >= 500:
                            reward_message += f"\n🏆 恭喜！您已拥有{new_count}个{type_name}，真是太厉害了！"
                        elif new_count >= 200:
                            reward_message += (
                                f"\n🌟 了不起！您的{type_name}已经达到{new_count}个！"
                            )
                        elif new_count >= 100:
                            reward_message += (
                                f"\n✨ 太棒了！您的{type_name}突破了100个！"
                            )
                        elif new_count in MILESTONE_VALUES:
                            reward_message += (
                                f"\n🎯 里程碑达成：{new_count}个{type_name}！"
                            )

                        await send_group_msg(
                            self.websocket,
                            self.group_id,
                            [
                                generate_reply_message(self.message_id),
                                generate_text_message(reward_message),
                                generate_text_message(ANNOUNCEMENT_MESSAGE),
                            ],
                            note="del_msg=10",
                        )

        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理发言奖励失败: {e}")

    async def handle(self):
        """
        处理群消息
        """
        try:
            # 处理群聊开关命令
            if await self._handle_switch_command():
                return

            # 处理菜单命令
            if await self._handle_menu_command():
                return

            # 如果没开启群聊开关，则不处理
            if not is_group_switch_on(self.group_id, MODULE_NAME):
                return

            # 处理特定命令
            if self.raw_message.startswith(SIGN_IN_COMMAND):
                # 黑名单用户
                if self.user_id in ["3649056059"]:
                    return
                await self._handle_sign_in_command()
                return
            if self.raw_message.startswith(SELECT_COMMAND):
                await self._handle_select_command()
                return
            if self.raw_message.startswith(QUERY_COMMAND):
                await self._handle_query_command()
                return
            # 排行榜命令需要精确匹配
            message_parts = self.raw_message.strip().split()
            if (len(message_parts) == 1 and message_parts[0] == RANKING_COMMAND) or (
                len(message_parts) == 2 and message_parts[0] == RANKING_COMMAND
            ):
                await self._handle_ranking_command()
                return
            if self.raw_message.startswith(LOTTERY_COMMAND):
                await self._handle_lottery_command()
                return

            # 处理普通发言奖励
            # 排除一些不应该获得奖励的消息类型
            excluded_patterns = [
                "签到",
                "选择",
                "查询",
                "排行榜",
                "抽阳光",
                "抽雨露",
                "抽太阳",
                "抽雨",
                "菜单",
                "help",
                "帮助",
                SWITCH_NAME.lower(),
                f"{SWITCH_NAME}{MENU_COMMAND}".lower(),
            ]

            # 检查消息是否为纯文本且不是命令
            if (
                self.raw_message.strip()
                and not any(
                    pattern in self.raw_message.lower() for pattern in excluded_patterns
                )
                and len(self.raw_message.strip()) >= 2
            ):  # 至少2个字符才给奖励

                await self._handle_speech_reward()

        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理群消息失败: {e}")
