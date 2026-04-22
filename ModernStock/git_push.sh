#!/bin/bash

# 1. Append the content of commit_msg to commit_msgs
echo -e "\n-----\n" >> commit_msgs
cat commit_msg >> commit_msgs

# 2. Stage all files
git add .

# 3. Remove all __pycache__ and ProjectLens directories from staging (without deleting actual files)
find . -type d -name "__pycache__" -exec git rm -r --cached {} +
git rm -r --cached ProjectLens

# 4. Commit using the content of commit_msg as the commit message
git commit -F commit_msg

# 5. Get the current branch name dynamically
current_branch=$(git symbolic-ref --short HEAD)

# 6. Push to the current branch (to avoid branch name mismatch issues)
git push origin "$current_branch"