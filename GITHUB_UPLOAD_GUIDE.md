# Publish VoyageAI on GitHub — Simple guide

1. Extract `VoyageAI-Smart-Trip-Planner-GitHub-Ready.zip` somewhere on your computer.
2. Open the extracted `VoyageAI-Smart-Trip-Planner` folder. **Do not add your `.env` file or `.venv` folder.**
3. Sign into https://github.com/ and select **New repository** (the `+` menu).
4. Repository name: `VoyageAI-Smart-Trip-Planner`. Description: `Agentic AI travel planner using LangGraph, Gemini, MCP, RAG, Tavily and Streamlit.`
5. Choose **Public** only if your college allows publicly sharing the code and reference materials; otherwise select **Private**. Leave **Add a README** unchecked because one already exists.
6. Create the repository. On its empty page click **uploading an existing file**.
7. Upload the **contents of the extracted project folder**, keeping `trip`, `data`, `tests`, `docs`, and `assets` as folders. GitHub website drag-and-drop accepts folders in supported browsers; if that fails, use GitHub Desktop or the terminal.
8. Double-check that `.env` and `.venv` were not uploaded. Commit with message `Initial release: VoyageAI Smart Trip Planner`.
9. Review the README on the repository home page: check that the diagrams and screenshots render.
10. Do not click Streamlit's **Deploy** unless you explicitly intend to host the app; publishing code is different from deploying a live application.

Optional git terminal approach (inside the extracted folder):

```bash
git init
git add .
git status
git commit -m "Initial release: VoyageAI Smart Trip Planner"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/VoyageAI-Smart-Trip-Planner.git
git push -u origin main
```

Before committing, always examine `git status` and confirm `.env`, `.venv`, and any downloaded private trip files are absent. Set up GitHub credentials if prompted.
