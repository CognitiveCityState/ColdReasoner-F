<div align="center">
    
[English](README.md) | [中文](README.zh.md)

</div>

<div align="center">

# ColdReasoner-F

**形式化行为验证 · 最小原型**

</div>

<div align="center">

[![Status](https://img.shields.io/badge/Status-Concept--Prototype-orange)](https://github.com/cold-os/ColdReasoner-F)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-blue.svg)](https://www.python.org/)
[![Z3](https://img.shields.io/badge/Z3-4.16.0-green.svg)](https://github.com/Z3Prover/z3)

</div>

ColdReasoner-F 是 ColdReasoner 运行时验证内核的**最小化精炼实现**。它以文件管理为场景，剥离哲学思辨，回归工程本质——**用Z3约束求解器，实现一个可运行、可验证的AI行为权限控制系统。**

系统核心机制为“信念-令牌-行为”的三步闭环：AI向CAGE网关报告意图（信念），CAGE校验合法性后发放令牌，AI凭令牌执行对应脚本。任何环节的偏离——信念非法、令牌滥用、行为越权——都将被ColdReasoner的数学约束捕获并拒绝。

> **⚠️ 设计定位**
>
> 本项目是一个**极简概念原型**，旨在将“信念-行为一致性”的校验思想，用Z3约束求解器精确编码为可判定的逻辑约束。它不是完整运行时系统，不涉及网络通信或真实权限管理，仅为验证逻辑内核的工程可行性而设计。

---

## 核心设计

```mermaid
flowchart LR
    subgraph 第一层 [信念校验]
        A[AI 报告信念] --> B{CAGE: 信念合法?}
        B -->|是| C[发放令牌]
        B -->|否| D[❌ 拦截]
    end

    subgraph 第二层 [行为校验]
        C --> E[AI 凭令牌执行脚本]
        E --> F{ColdReasoner: 行为匹配?}
        F -->|是| G[✅ 执行通过]
        F -->|否| H[❌ 拦截]
    end
```

### 场景定义

系统管理一个“文件系统”，定义如下行为与信念的闭集：

| 类型 | 信念/行为 | 状态 |
|------|-----------|------|
| 合法信念 | READ, WRITE | ✅ 允许报告 |
| 非法信念 | DELETE, MODIFY | ❌ 禁止报告 |
| 合法动作 | READ, WRITE | ✅ 允许执行（且受时序约束） |
| 有条件动作 | DELETE | ⚠️ 允许执行，但必须此前有过 READ |
| 非法动作 | MODIFY | ❌ 永久禁止执行 |

### 校验规则

**规则1：信念合法性**：只有 READ 和 WRITE 可作为信念被报告；DELETE 和 MODIFY 作为信念被永久禁止。

**规则2：信念-行为映射**（正向蕴含）：报告信念 READ 允许执行 READ 或 DELETE 动作；报告信念 WRITE 只允许执行 WRITE 动作。不设置反向强制映射（即执行 DELETE 不强制要求报告 DELETE）。

**规则3：时序约束**：
- 执行 DELETE 动作之前，历史轨迹中必须至少有一次 READ 动作。
- 禁止连续两次执行 WRITE 动作。

**规则4：令牌发放**：校验通过后，CAGE 发放一个包含对应权限范围的实体令牌（Token），令牌可被撤销。

---

## 快速开始

### 环境要求

- Python 3.8+
- Z3 Solver

### 安装与运行

```bash
pip install z3-solver
python cold_reasoner_f.py
```

### 输出示例

```
=== 运行时增量校验 ===

--- Step 1: belief=READ, action=READ ---
[EXEC] READ test.txt
✅ 校验通过，令牌 T-0 发放

--- Step 2: belief=WRITE, action=WRITE ---
[EXEC] WRITE test.txt with 'new content'
✅ 校验通过，令牌 T-1 发放

--- Step 3: belief=READ, action=DELETE ---
[EXEC] DELETE test.txt
✅ 校验通过，令牌 T-2 发放

--- Step 4: belief=WRITE, action=WRITE ---
[EXEC] WRITE test.txt with 'new content'
✅ 校验通过，令牌 T-3 发放

--- Step 5: belief=READ, action=READ ---
[EXEC] READ test.txt
✅ 校验通过，令牌 T-4 发放
```

### 结果解读

| 结果 | 含义 |
|------|------|
| `sat` | 存在一组合法的信念-行为组合，满足所有约束 |
| `unsat` | 当前假设违反至少一条规则，被 CAGE/ColdReasoner 拦截 |

---

## 从论文到代码：演进说明

本项目是对先前 ColdReasoner 概念的**工程化精炼**：

| 维度 | 先前设计 (ColdReasoner) | 本实现 (ColdReasoner-F) |
|------|-------------------------|------------------------|
| 校验层数 | 三层（信念合法性 / 行为自洽 / 近似一致性） | 静态规则（信念合法性 + 正向映射）+ 时序约束 |
| 映射关系 | 近似相等（语义距离） | 一对多正向映射（READ → READ/DELETE，WRITE → WRITE） |
| 时序逻辑 | 未覆盖 | 支持基于历史轨迹的约束（如 DELETE 前置 READ） |
| 令牌机制 | 隐含 | 实体令牌对象（含 scope、revoked 等属性） |
| 执行钩子 | 无 | 校验通过后调用真实预置脚本 |
| 哲学思辨 | 包含冷存在模型等背景 | 完全剥离，纯工程表达 |

本实现保留了 ColdReasoner 的核心思想——**通过外部契约约束AI行为**——但将其形式化为可运行、可验证、可审计的数学约束。

---

## 核心局限

### 逻辑表达力
当前仅包含简单的时序约束（基于历史轨迹的有限规则），尚未支持通用的 LTL/CTL 属性验证；模态逻辑未覆盖。

### 场景范围
仅针对文件读/写/删/改这一特定场景设计，泛化到其他领域（如对话系统、自主Agent）需重新定义信念空间、行为空间与映射关系。

### 实际部署
未集成操作系统权限管理，仅为概念验证原型，不适用于生产环境。

---

## LLM 集成测试

除纯净的核心验证引擎（`cold_reasoner_f.py`）外，本项目还提供了一个集成演示文件 `llm_integration_demo.py`。该文件调用核心引擎，并与阿里云百炼平台的 **qwen-plus** 模型对接，模拟智能体在形式化约束下的决策过程。

运行该测试前，请先设置环境变量 `DASHSCOPE_API_KEY`，然后执行：

```bash
pip install dashscope
python llm_integration_demo.py
```

测试套件包含四个独立场景，分别验证：
1. **信念-动作映射违规**（READ → MODIFY 被拦截）
2. **时序约束违规**（未读先删被拦截）
3. **时序约束违规**（连续 WRITE 被拦截）
4. **非结构化输入鲁棒性**（自然语言输入被安全拒绝）

当前版本所有测试均通过，输出示例如下（精简）：

```
[测试1] 预期拦截: READ 信念不允许 MODIFY 动作  → ✅ 拦截成功
[测试2] 预期拦截: DELETE 前无 READ            → ✅ 拦截成功
[测试3] 预期拦截: 连续 WRITE 两次             → ✅ 拦截成功
[测试4] 预期拦截: 自然语言输出，解析失败       → ✅ 系统安全失败
```

该集成演示充分验证了 ColdReasoner-F 内核在真实 LLM 交互场景下的可靠性，同时保持核心引擎的独立性与纯净性。

---

## 人工智能使用声明

本项目的代码实现由人类作者与 AI 辅助工具协作完成。

**人类作者贡献**：
- 核心架构设计：信念-令牌-行为的闭环模型
- 校验规则的逻辑定义（两层校验、精确匹配取代近似）
- 场景抽象与测试用例设计

**AI 辅助贡献**：
- 代码实现与调试
- 语法修正与格式优化
- 测试用例生成

最终代码的正确性与工程责任由人类作者承担。

---

## 技术栈

- **约束求解器**: Z3 4.16.0
- **语言**: Python 3.8+

---

## 下一步扩展方向

- 集成 LLM 接口，使“信念”来自模型实时输出
- 增加文件系统状态的动态变化（如“文件已存在”等前置条件）
- 扩展校验规则，支持时序约束与依赖关系
- 替换 Z3 为运行时监控引擎，实现连续校验而非单次判定

---

## 许可证

Apache 2.0
