# Decision-Orchestration Agent

Coordinates the Feasibility, CostImpact, Explanation, and RiskAssessment sub-agents. Accepts requests from UI or other services and delegates to sub-agents for analysis and recommendations.

Responsibilities:
- Aggregate risk signals from `inventory` agent
- Call subagents: Feasibility, CostImpact, Explanation, RiskAssessment
- Produce recommendations and explanations

This folder contains placeholder stubs to help show the repository structure.