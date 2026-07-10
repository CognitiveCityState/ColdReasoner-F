from z3 import *

# =============================================
# 1. 场景定义：文件管理系统
# 合法：读(READ)、写(WRITE)
# 非法：删(DELETE)、改(MODIFY)
# =============================================

# 信念（AI向CAGE声称要做的事）
B_READ, B_WRITE, B_DELETE, B_MODIFY = 0, 1, 2, 3
# 行为（AI实际通过脚本执行的操作）
A_READ, A_WRITE, A_DELETE, A_MODIFY = 10, 11, 12, 13

belief_names = {0: 'READ', 1: 'WRITE', 2: 'DELETE', 3: 'MODIFY'}
action_names = {10: 'READ', 11: 'WRITE', 12: 'DELETE', 13: 'MODIFY'}

beliefs = [B_READ, B_WRITE, B_DELETE, B_MODIFY]
actions = [A_READ, A_WRITE, A_DELETE, A_MODIFY]

# 定义四个闭集（合法信念/行为，非法信念/行为）
legal_beliefs_set = [B_READ, B_WRITE]
illegal_beliefs_set = [B_DELETE, B_MODIFY]
legal_actions_set = [A_READ, A_WRITE]
illegal_actions_set = [A_DELETE, A_MODIFY]

# 信念与行为的精确映射
match_action = {
    B_READ: A_READ,
    B_WRITE: A_WRITE,
    B_DELETE: A_DELETE,
    B_MODIFY: A_MODIFY
}
match_belief = {v: k for k, v in match_action.items()}

# =============================================
# 2. 核心校验引擎 (ColdReasoner + CAGE)
# =============================================

report = {b: Bool(f'report_{belief_names[b]}') for b in beliefs}
execute = {a: Bool(f'execute_{action_names[a]}') for a in actions}
token_granted = Bool('token_granted')

solver = Solver()

# ----- 互斥约束：每次只能报告一个信念，也只能执行一个行为 -----
# 对信念做两两互斥
for i in range(len(beliefs)):
    for j in range(i+1, len(beliefs)):
        solver.add(Not(And(report[beliefs[i]], report[beliefs[j]])))
# 对行为做两两互斥
for i in range(len(actions)):
    for j in range(i+1, len(actions)):
        solver.add(Not(And(execute[actions[i]], execute[actions[j]])))

# ================= 第一层校验：信念合法性 =================
# 非法信念绝对不能被报告
for b in illegal_beliefs_set:
    solver.add(Not(report[b]))

# ================= CAGE 令牌发放逻辑 =================
# 当且仅当报告了一个合法信念时，CAGE才发放令牌
has_legal_report = Or([report[b] for b in legal_beliefs_set])
solver.add(token_granted == has_legal_report)

# ================= 第二层校验：行为执行力 =================
# 规则：信念为X则行为只能为X（严格等价）

# 正向：报告信念 -> 必须执行对应的精确行为
for b in beliefs:
    solver.add(Implies(report[b], execute[match_action[b]]))

# 反向：执行行为 -> 必须此前报告了对应信念
for a in actions:
    solver.add(Implies(execute[a], report[match_belief[a]]))

# 额外硬边界：绝不能执行非法行为闭集中的行为
for a in illegal_actions_set:
    solver.add(Not(execute[a]))

# =============================================
# 3. 测试验证：完整流程演示
# =============================================

def run_test(description, assumptions):
    print(f"=== {description} ===")
    solver.push()
    if assumptions:
        solver.add(assumptions)
    status = solver.check()
    print(f"校验结果: {status}")
    if status == sat:
        model = solver.model()
        reported = [belief_names[b] for b in beliefs if model[report[b]]]
        executed = [action_names[a] for a in actions if model[execute[a]]]
        print(f"  [AI报告信念]: {reported if reported else '无'}")
        print(f"  [CAGE令牌状态]: {'发放' if model[token_granted] else '未发放'}")
        print(f"  [实际执行脚本]: {executed if executed else '无'}")
        if reported and executed:
            print(f"  ✅ 流程闭环: 信念({reported[0]}) -> 令牌 -> 执行({executed[0]}) 匹配")
    else:
        print("  ❌ 流程被 CAGE/ColdReasoner 拦截: 检测到非法行为或信念")
    solver.pop()
    print()

# ----- 测试用例 -----
run_test("测试1 (通过): 流程闭环 (READ)",
         [report[B_READ] == True, execute[A_READ] == True])

run_test("测试2 (拦截): 信念非法 (DELETE)",
         [report[B_DELETE] == True])

run_test("测试3 (拦截): 信念-行为不匹配 (READ vs DELETE)",
         [report[B_READ] == True, execute[A_DELETE] == True])

run_test("测试4 (拦截): 执行非法脚本 (MODIFY)",
         [report[B_WRITE] == True, execute[A_MODIFY] == True])

run_test("测试5 (通过): 空闲状态",
         [And([Not(report[b]) for b in beliefs] + [Not(execute[a]) for a in actions])])