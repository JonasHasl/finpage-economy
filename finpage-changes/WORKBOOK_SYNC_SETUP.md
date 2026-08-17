# Workbook sync and deployment walkthrough

## What this change does

The app keeps using `src/AlgoComposition.xlsx` locally unless `ALGO_WORKBOOK_BACKEND=github` is set. [workbook store](src/workbook_store.py)

With the GitHub backend enabled, the app downloads the workbook to a temporary cache on first use, reloads the latest GitHub copy immediately before each save, and uploads the new workbook before replacing its cache. [workbook store](src/workbook_store.py)

The upload includes GitHub's current file SHA, so GitHub rejects a save if somebody else changed the workbook first instead of silently overwriting their update. [GitHub Contents API](https://docs.github.com/en/rest/repos/contents)

## One-time setup

1. Create a new private GitHub repository named `finpage-data` with a README, which creates its `main` branch. Keep this repository separate from the Render-connected code repository so workbook commits cannot satisfy Render's linked-branch deployment trigger. [Render deployment behavior](https://render.com/docs/deploys)

2. Create a fine-grained GitHub personal-access token that can access only `finpage-data`, with **Contents: Read and write** permission. Do not put the token in this repository. [GitHub token guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) [GitHub Contents API permissions](https://docs.github.com/en/rest/repos/contents)

3. In Render, open the existing web service's **Settings** page and set Auto-Deploy to **Off** before pushing this code. This prevents a Git push from starting a deployment automatically. [Render auto-deploy settings](https://render.com/docs/deploys)

4. In Render's **Environment** page, add the variables below and choose **Save only**. This stores the configuration without deploying the currently live service. [Render environment variables](https://render.com/docs/configure-environment-variables)

   ```text
   ALGO_WORKBOOK_BACKEND=github
   GITHUB_WORKBOOK_REPOSITORY=YOUR_GITHUB_USERNAME/finpage-data
   GITHUB_WORKBOOK_TOKEN=the_fine_grained_token
   GITHUB_WORKBOOK_BRANCH=main
   GITHUB_WORKBOOK_PATH=AlgoComposition.xlsx
   GITHUB_WORKBOOK_BOOTSTRAP_FROM_LOCAL=true
   ```

5. Push the reviewed code when you are ready, then use **Manual Deploy** in Render. On its first workbook read, the app will create `AlgoComposition.xlsx` in the empty data repository from the verified workbook bundled in this commit. [GitHub create-or-update contents API](https://docs.github.com/en/rest/repos/contents) [Render manual deploys](https://render.com/docs/deploys)

6. Confirm the Algo-helper tables match the backup, submit one intentional change, and verify that a new commit appears in `finpage-data`. After that check, set `GITHUB_WORKBOOK_BOOTSTRAP_FROM_LOCAL=false` with **Save only** for the next deployment. [workbook store](src/workbook_store.py)

## Normal operation and recovery

Every successful Algo-helper save updates the data repository first, and then the application cache. [workbook store](src/workbook_store.py)

If GitHub is unavailable or a conflict is detected, the page shows an error and leaves the last durable workbook unchanged. [workbook store](src/workbook_store.py)

Do not use a push to the code repository as a way to update the workbook after this migration; update the table in the app, and the app will create the data-repository commit automatically. [workbook store](src/workbook_store.py)
