# GitHub Copilot Custom Instructions

## Project Development Guidelines

### Follow PLAN.MD for All Development

When working on this project, **always reference and follow PLAN.MD** for:

1. **Architecture & Design Decisions**: 
   - Follow the technical architecture defined in Section 3 (PostGIS Database Schema)
   - Use the exact data sources and APIs specified in Section 2
   - Implement modules as outlined in the project structure (Section 1)

2. **Development Roadmap**: 
   - Follow the phased implementation approach defined in Section 12
   - Complete phases in order: Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10
   - Ensure each phase's deliverables are complete before moving to next phase

3. **Track Progress in PLAN.MD**:
   - **Update phase status** in PLAN.MD as work progresses:
     - Mark phases as ✅ when fully completed
     - Mark phases as 🔄 when currently in progress
     - Keep phases as ⬜ when not yet started
   - Update the "Phase Summary & Timeline" table at the end of PLAN.MD
   - Document any deviations from the plan with explanations

4. **Code Standards**:
   - Use exact naming conventions from PLAN.MD (file names, function names, table names)
   - Follow the SQL schema definitions exactly (Section 3.2)
   - Implement data validation and error handling as specified
   - Use the configuration structure defined in `config/settings.py` (Section 9)

5. **Data Sources & APIs**:
   - Use only the approved data sources listed in Section 2
   - Respect rate limits and implement retries as specified
   - Follow the exact API endpoints and parameters documented

6. **Testing & Verification**:
   - Run the verification queries specified for each phase
   - Ensure "Definition of Done" criteria are met before marking phases complete
   - Write tests as outlined in Phase 10

## Development Workflow

When implementing new features or fixing issues:
1. Check current phase status in PLAN.MD
2. Read the relevant section for technical specifications
3. Implement according to the plan
4. Update PLAN.MD to reflect completion status
5. Commit changes with reference to phase/section

## Important Notes

- PLAN.MD is the **source of truth** for this project
- Any changes to architecture or approach should be documented in PLAN.MD first
- Keep PLAN.MD updated as the single source of documentation for project progress
