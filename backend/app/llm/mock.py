"""Deterministic M2 fixtures. This is not a language model or an evaluator."""
FRONTEND = [
    ('浏览器基础', '浏览器从输入 URL 到显示页面，主要经历哪些步骤？'),
    ('响应式界面', '你会用怎样的布局让同一页面适配不同屏幕？'),
    ('JavaScript', '请用一个例子解释 JavaScript 的事件循环。'),
    ('Vue 状态', '组件之间共享状态时，你会怎样选择 props 和状态管理？'),
    ('接口交互', '请求失败时，页面应该如何保留用户输入并提供重试？'),
    ('性能', '页面加载较慢时，你会先测量哪个指标？'),
    ('工程化', '请介绍你理解的类型检查、构建与测试之间的区别。'),
    ('可访问性', '一个表单如何让键盘用户也能顺利完成操作？'),
    ('并发交互', '快速切换用户或页面时，怎样防止旧请求覆盖新数据？'),
    ('项目取舍', '请举例说明一次界面实现中的技术取舍。'),
]
BACKEND = [
    ('数据库基础', '请用一个例子说明数据库事务的作用。'),
    ('接口设计', '创建资源时，为什么要区分参数错误、权限错误和状态冲突？'),
    ('并发控制', '两个请求同时修改一份资料，你会怎样避免互相覆盖？'),
    ('索引', '数据库索引为什么能加速查询？'),
    ('幂等', '网络重试导致同一请求被重复发送时，你会怎样处理？'),
    ('缓存', '你会如何处理缓存和数据库之间的数据一致性问题？'),
    ('权限', '接口接收到一个资源 ID 后，怎样确认当前用户有权读取？'),
    ('异步任务', '长任务为什么不应该一直占用一个数据库事务？'),
    ('故障恢复', '进程突然退出后，如何知道任务未完成，而不是误报成功？'),
    ('系统取舍', '请说明一个后端项目中的设计选择适用于什么场景。'),
]
BEHAVIORAL = [
    '请举例说明你在团队项目中采取的一项关键行动。',
    '团队意见不一致时，你做过什么来推动合作？',
    '请讲述一次遇到困难后调整实现方案的经历。',
    '请举例说明你如何验证自己掌握了一项新技术。',
    '请介绍一次你主动发现并解决问题的经历。',
    '收到反馈后，你做过什么来落实改进？',
    '多个任务同时临近截止时，你如何确定优先级？',
    '请描述一次你向他人解释复杂技术问题的经历。',
    '项目结果未达到预期时，你如何复盘？',
    '你希望下一份实习或工作重点提升什么能力？',
]
PRESSURE = [
    '哪项成果最能体现你对项目的贡献？',
    '你说方案有效，如何说明这是你的方案带来的结果？',
    '如果工期缩短一半，你会优先保留哪项需求？',
    '如果面试官不同意你的设计，你会如何回应？',
    '你的方案最可能在什么条件下失败？',
    '面对一个你暂时不会的问题，你会怎样说明已知与未知？',
    '如果团队否决你的建议，你会如何推进后续工作？',
    '和更简单的方案相比，你的实现主要增加了什么成本？',
    '一个关键依赖突然不可用时，你会如何调整计划？',
    '哪项证据最能支持你的结论？',
]


class MockProvider:
    def question(self, role: str, mode: str, ordinal: int) -> tuple[str, str]:
        if mode == 'behavioral':
            return '行为表达', BEHAVIORAL[ordinal - 1]
        if mode == 'pressure':
            return '观点与依据', PRESSURE[ordinal - 1]
        if role in {'frontend', 'backend'}:
            return (FRONTEND if role == 'frontend' else BACKEND)[ordinal - 1]
        from app.agent.context_builder import seed_question
        from app.core.roles import ROLE_BY_ID
        seed = seed_question(role, mode, ordinal)
        return seed['topic'], f"请举例说明「{seed['topic']}」如何用于{ROLE_BY_ID[role]['label']}的一项日常任务。"

    def followup(self, answer: str, used: int, budget: int) -> str | None:
        if len(answer) < 50 and used < budget:
            return '这是固定 Mock 追问：请用一个具体例子补充刚才的回答。'
        return None

    def hint(self) -> str:
        return 'Mock 提示：可以依次说明「是什么、为什么、具体例子、适用边界」。不确定的部分可以如实说明。'
