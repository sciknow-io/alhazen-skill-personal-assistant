# alhazen-skill-personal-assistant

Personal-assistant skills for the [Alhazen](https://github.com/sciknow-io/skillful-alhazen) TypeDB-powered notebook. These skills **share one TypeDB database, `alh_personal`**.

## Skills

| Skill | Purpose | Namespace |
|-------|---------|-----------|
| **jobhunt** | Track job applications, analyze positions, identify skill gaps, plan search strategy | `jhunt-` |
| **coach** | Personal health & fitness monitoring — HealthKit metrics, goals, regressions, appointments | `coach-` |

## Install

Requires the Alhazen base pair from the [`skillful-alhazen`](https://github.com/sciknow-io/skillful-alhazen) marketplace (`alhazen-core` + `typedb-notebook`), which install automatically as cross-marketplace dependencies.

```
/plugin marketplace add sciknow-io/skillful-alhazen
/plugin marketplace add sciknow-io/alhazen-skill-personal-assistant
/plugin install jobhunt@alhazen-personal-assistant
```
