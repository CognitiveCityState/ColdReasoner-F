"""
ColdReasoner-F: 运行时形式化验证内核原型

本实现演示了如何将形式化验证（Z3）与运行时监控相结合，
构建一个独立于AI模型的确定性安全层。核心特性包括：

1. 执行钩子（Execution Hooks）：将验证通过的动作与真实脚本绑定
2. 离线属性验证（Offline Verification）：启动时检查规则一致性
3. 时序逻辑（Temporal Logic）：基于历史轨迹的约束（如"DELETE前必须READ"）
4. 令牌实质化（Token Substantiation）：将权限抽象为可撤销的对象
5. 增量式轨迹检查（Incremental Checking）：每步仅依赖历史摘要，无状态污染

"""

from z3 import *
from dataclasses import dataclass
from typing import List, Optional
import time

# ============================================================================
# 1. 预置脚本（模拟实际系统调用）
#    此处定义的是系统实际执行的操作，AI 无法绕过此层。
# ============================================================================

def do_read(file: str) -> str:
    """模拟文件读取，返回内容"""
    print(f"[EXEC] READ {file}")
    return f"Content of {file}"

def do_write(file: str, content: str) -> None:
    """模拟文件写入"""
    print(f"[EXEC] WRITE {file} with '{content}'")

def do_delete(file: str) -> None:
    """模拟文件删除"""
    print(f"[EXEC] DELETE {file}")

def do_modify(file: str, new_content: str) -> None:
    """模拟文件修改（在此原型中为永久非法动作）"""
    print(f"[EXEC] MODIFY {file} to '{new_content}'")

# 动作名到函数的映射（执行钩子的核心）
ACTION_FUNCS = {
    'READ': do_read,
    'WRITE': do_write,
    'DELETE': do_delete,
    'MODIFY': do_modify,
}


# ============================================================================
# 2. 令牌实质化（Capability-based Token）
#    令牌代表授予 AI 的权限，可被撤销，且绑定特定的动作范围。
# ============================================================================

@dataclass
class Token:
    id: str                     # 唯一标识
    scope: List[str]            # 允许的动作列表
    granted_at: float           # 发放时间（可用于过期策略）
    revoked: bool = False       # 是否已被撤销

    def is_valid(self, action: str) -> bool:
        """检查令牌是否有效且允许该动作"""
        return not self.revoked and action in self.scope


# ============================================================================
# 3. 离线属性验证（设计时）
#    在系统启动前，检查规则集是否存在内部矛盾。
#    此版本因采用一对多映射，不再强制单射，故仅做占位演示。
# ============================================================================

def offline_verify_rules():
    """
    设计时规则验证（当前跳过，因为一对多映射无需单射性检查）
    实际可扩展为：检查非法信念与合法动作是否重叠、规则是否自相矛盾等。
    """
    print("[Offline] 规则映射检查已跳过（本原型允许一对多映射）")


# ============================================================================
# 4. 核心校验引擎（ColdReasoner-F）
# ============================================================================

class ColdReasonerF:
    """
    运行时验证器，处理每一条 AI 的“信念-行为”对。
    使用 Z3 求解器进行约束检查，并维护历史轨迹用于时序约束。
    """

    def __init__(self):
        # --- 枚举定义 ---
        self.B_READ, self.B_WRITE, self.B_DELETE, self.B_MODIFY = 0, 1, 2, 3
        self.A_READ, self.A_WRITE, self.A_DELETE, self.A_MODIFY = 10, 11, 12, 13
        self.belief_names = {0: 'READ', 1: 'WRITE', 2: 'DELETE', 3: 'MODIFY'}
        self.action_names = {10: 'READ', 11: 'WRITE', 12: 'DELETE', 13: 'MODIFY'}
        self.beliefs = [self.B_READ, self.B_WRITE, self.B_DELETE, self.B_MODIFY]
        self.actions = [self.A_READ, self.A_WRITE, self.A_DELETE, self.A_MODIFY]

        # --- 安全策略定义 ---
        # 合法信念：AI 可以报告 READ 或 WRITE（DELETE/MODIFY 作为信念被永久禁止）
        self.legal_beliefs = [self.B_READ, self.B_WRITE]
        # 非法行为：MODIFY 被永久禁止（DELETE 受时序约束，允许在条件下执行）
        self.illegal_actions = [self.A_MODIFY]

        # 信念 -> 允许的动作集合（一对多映射）
        # READ 信念可执行 READ 或 DELETE；WRITE 信念只能执行 WRITE
        self.belief_allowed_actions = {
            self.B_READ: [self.A_READ, self.A_DELETE],
            self.B_WRITE: [self.A_WRITE],
        }

        # --- 运行时状态 ---
        self.trajectory: List[dict] = []      # 历史轨迹，用于时序约束
        self.solver = Solver()                # Z3 求解器（全局静态规则）
        self._init_static_constraints()

        # --- 令牌管理 ---
        self.tokens: List[Token] = []
        self.token_counter = 0

    def _init_static_constraints(self):
        """
        初始化与具体步骤无关的约束，这些约束在整个系统生命周期内保持不变。
        """
        s = self.solver

        # 信念互斥（同一时刻只能有一个信念为真）
        for i in range(len(self.beliefs)):
            for j in range(i+1, len(self.beliefs)):
                s.add(Not(And(Bool(f'rep_{self.beliefs[i]}'), Bool(f'rep_{self.beliefs[j]}'))))

        # 行为互斥（同一时刻只能执行一个动作）
        for i in range(len(self.actions)):
            for j in range(i+1, len(self.actions)):
                s.add(Not(And(Bool(f'exe_{self.actions[i]}'), Bool(f'exe_{self.actions[j]}'))))

        # 非法信念：DELETE 和 MODIFY 作为信念被永久禁止
        for b in [self.B_DELETE, self.B_MODIFY]:
            s.add(Not(Bool(f'rep_{b}')))

        # 非法行为：MODIFY 被永久禁止
        for a in self.illegal_actions:
            s.add(Not(Bool(f'exe_{a}')))

        # 信念 -> 允许动作（正向蕴含）
        for belief, allowed_actions in self.belief_allowed_actions.items():
            s.add(Implies(Bool(f'rep_{belief}'), Or([Bool(f'exe_{a}') for a in allowed_actions])))

    # ---------- 字符串 ↔ 枚举 辅助方法 ----------
    def belief_from_str(self, s: str) -> int:
        """将信念字符串转换为枚举值（不区分大小写）"""
        mapping = {'READ': self.B_READ, 'WRITE': self.B_WRITE,
                   'DELETE': self.B_DELETE, 'MODIFY': self.B_MODIFY}
        return mapping.get(s.upper(), None)

    def action_from_str(self, s: str) -> int:
        """将动作字符串转换为枚举值（不区分大小写）"""
        mapping = {'READ': self.A_READ, 'WRITE': self.A_WRITE,
                   'DELETE': self.A_DELETE, 'MODIFY': self.A_MODIFY}
        return mapping.get(s.upper(), None)

    def issue_token(self, belief: int) -> Token:
        """根据信念生成一个令牌，其 scope 包含该信念允许的所有动作"""
        allowed = self.belief_allowed_actions.get(belief, [])
        token = Token(
            id=f"T-{self.token_counter}",
            scope=[self.action_names[a] for a in allowed],
            granted_at=time.time(),
            revoked=False
        )
        self.token_counter += 1
        self.tokens.append(token)
        return token

    def revoke_token(self, token_id: str) -> None:
        """撤销指定的令牌"""
        for t in self.tokens:
            if t.id == token_id:
                t.revoked = True
                print(f"[REVOKE] Token {token_id} revoked")
                break

    def run_step(self, reported_belief: int, executed_action: int) -> bool:
        """
        处理一个步骤：检查信念-行为对是否满足所有静态规则和时序约束。
        若通过，则发放令牌、执行实际动作并记录轨迹；否则拦截。
        返回 True 表示通过，False 表示被拦截。
        """
        # 临时保存静态规则上下文，并添加当前步的赋值
        self.solver.push()

        # 设置当前步的变量赋值
        for b in self.beliefs:
            self.solver.add(Bool(f'rep_{b}') == (b == reported_belief))
        for a in self.actions:
            self.solver.add(Bool(f'exe_{a}') == (a == executed_action))

        # 时序约束（基于历史轨迹）
        # 规则1：执行 DELETE 必须在此之前至少执行过一次 READ
        if executed_action == self.A_DELETE:
            past_read = any(step['action'] == 'READ' for step in self.trajectory)
            if not past_read:
                self.solver.add(False)   # 使当前步不可满足

        # 规则2：禁止连续两次 WRITE
        if executed_action == self.A_WRITE and self.trajectory:
            if self.trajectory[-1]['action'] == 'WRITE':
                self.solver.add(False)

        # 执行求解
        status = self.solver.check()

        # 清除当前步的赋值（恢复静态规则）
        self.solver.pop()

        if status == sat:
            # 校验通过：发放令牌，记录轨迹，执行钩子
            token = self.issue_token(reported_belief)
            self.trajectory.append({
                'belief': self.belief_names[reported_belief],
                'action': self.action_names[executed_action],
                'token_id': token.id
            })

            # 调用预置脚本（执行钩子）
            action_name = self.action_names[executed_action]
            action_func = ACTION_FUNCS.get(action_name)
            if action_func:
                # 为演示简单传参（实际应使用上下文数据）
                if action_name == 'READ':
                    action_func("test.txt")
                elif action_name == 'WRITE':
                    action_func("test.txt", "new content")
                elif action_name == 'DELETE':
                    action_func("test.txt")
                elif action_name == 'MODIFY':
                    action_func("test.txt", "modified")

            print(f"✅ 校验通过，令牌 {token.id} 发放")
            return True
        else:
            print("❌ 校验失败，拦截")
            return False

    def close(self):
        """清理资源（原型中无额外操作）"""
        pass


# ============================================================================
# 5. 演示主程序
# ============================================================================

if __name__ == "__main__":
    # 启动离线验证（设计时检查）
    offline_verify_rules()

    # 创建运行时验证器
    reasoner = ColdReasonerF()

    # 定义一组测试步骤（信念, 行为）
    test_cases = [
        (reasoner.B_READ, reasoner.A_READ),        # READ → READ，应通过
        (reasoner.B_WRITE, reasoner.A_WRITE),      # WRITE → WRITE，应通过
        (reasoner.B_READ, reasoner.A_DELETE),      # READ → DELETE，历史有READ，通过
        (reasoner.B_WRITE, reasoner.A_WRITE),      # WRITE → WRITE，上一步是DELETE，非连续，通过
        (reasoner.B_READ, reasoner.A_READ),        # READ → READ，通过
    ]

    print("\n=== 运行时增量校验 ===")
    for idx, (b, a) in enumerate(test_cases, 1):
        print(f"\n--- Step {idx}: belief={reasoner.belief_names[b]}, action={reasoner.action_names[a]} ---")
        reasoner.run_step(b, a)

    # 展示颁发的令牌
    print("\n=== 当前令牌 ===")
    for t in reasoner.tokens:
        print(f"  {t.id} scope={t.scope} revoked={t.revoked}")

    # 演示撤销功能
    if reasoner.tokens:
        reasoner.revoke_token(reasoner.tokens[0].id)

    reasoner.close()
