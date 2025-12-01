# 🚀 AI-Powered PI Planning Assistant

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Azure DevOps](https://img.shields.io/badge/Azure%20DevOps-0078D7?logo=azure-devops&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?logo=openai&logoColor=white)

An intelligent assistant that automates and optimizes the **PI Planning** process for Agile teams using **Azure DevOps** and **Generative AI**.

---

## 🎯 What does it do?

Planning a Program Increment (PI) involves juggling hundreds of User Stories, Dependencies, Team Capacities, and Milestones. This tool acts as an **AI Program Manager** that:

1.  **Fetches Data**: Pulls Features and User Stories directly from Azure DevOps.
2.  **Optimizes Schedule**: Automatically sequences User Stories based on:
    *   Feature Deadlines (Target Dates)
    *   Dependencies (Features & Stories)
    *   WSJF (Weighted Shortest Job First)
    *   Cost of Delay
3.  **Negotiates with Teams**: Uses intelligent strategies to fit work into Sprints based on team capacity and availability.
4.  **Identifies Risks**: Detects overdue items, capacity overflows, and broken dependencies using both deterministic rules and AI analysis.
5.  **Visualizes the Plan**: Generates a Program Board, Dependency Graphs, and Capacity Charts.

## ✨ Key Features

*   **🔌 Azure DevOps Integration**: Seamlessly fetches work items via ADO API.
*   **🧠 Strategy-Driven Planning**: 
    *   **Dependency Aware Strategy**: Prioritizes dependencies to ensure feasible schedules.
    *   **Standard Prioritization**: Sorts work by Target Date, Deadline Sprint, and Cost of Delay.
*   **🤖 Hybrid AI**: Enhances reporting, objective generation, and qualitative risk analysis with LLM insights (optional).
*   **📊 Interactive UI**: Built with Streamlit for real-time planning visualization.
*   **📈 Visualization**:
    *   **Dependency Graph**: Interactive network graph of Features and Stories.
    *   **Capacity Heatmaps**: See team load across sprints.
    *   **Timeline**: Gantt-style view of feature delivery.
*   **⚙️ Fully Configurable**: Customize sprint schedules, team names, and ADO field mappings via `config.yaml`.

## 🚀 Quick Start

### Prerequisites

*   Python 3.9+
*   Azure DevOps Account (and a Personal Access Token)
*   (Optional) Azure OpenAI Key for AI features

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/planning-ai.git
    cd planning-ai
    ```

2.  **Install dependencies**
    ```bash
    pip install .
    # OR just install requirements
    pip install -r requirements.txt
    ```

3.  **Configure**
    Copy `config.yaml` (it will be created on first run) or create one:
    ```yaml
    ado:
      org_url: "https://dev.azure.com/YOUR_ORG"
      pat: "YOUR_PAT_TOKEN"
      project: "YOUR_PROJECT"
    ```

4.  **Run the App**
    ```bash
    streamlit run src/ui/streamlit_app.py
    ```

## ⚙️ Configuration (`config.yaml`)

The application is highly customizable. You can map ADO fields to your process template:

```yaml
ado_mapping:
  effort: "Microsoft.VSTS.Scheduling.StoryPoints"
  priority: "Microsoft.VSTS.Common.Priority"
  target_date: "System.TargetDate"

defaults:
  sprints:
    count: 5
    length_weeks: 2
  teams:
    - name: "Team A"
      default_capacity: 40
```

## 🏗️ Architecture

The project follows a modular, event-driven architecture:

*   **`src/agents`**: 
    *   **Program Manager**: Orchestrates the planning process using strategies.
    *   **Team Agent**: Manages team capacity and validates assignments.
    *   **Data Agent**: Interfaces with Azure DevOps.
    *   **Reporting/Risk/Objective Agents**: Generate value-add outputs.
*   **`src/core`**: 
    *   **Strategies**: Pluggable algorithms for Prioritization and Planning.
    *   **Events**: Event-driven communication system.
    *   **Models**: Pydantic data models.
*   **`src/ui`**: Streamlit-based user interface.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
