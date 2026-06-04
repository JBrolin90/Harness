# Memory
## Personal

### Development Workflow ( Joachim reminded me multiple times - MUST follow )
1. **Features go on feature branches, not directly on dev**
   - Create feature branches: `git checkout -b feature/<feature-name>`
   - Commit changes there, not on dev
   - This is a clear and established rule that I have failed to follow at least once

2. **Read plan.txt for context** when the user mentions a plan

3. **Check existing branches** before creating new ones

4. **Do not pollute stdout with debug output** - use the debug logging system instead

### Project-Specific
- Harness project: /home/joachim/lab/prj/Harness
- Main branch: main, dev branch: dev
- Provider config: providers.json
- Feature branches pattern: feature/<name>
