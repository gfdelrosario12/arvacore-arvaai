# Tasks: AI Chat History, Context Retrieval, and Implementation Plan Lifecycle Management

## Implementation Tasks

- [x] 1. **Database Schema & Migrations**
  - [x] 1.1 Create migration `V26__chat_history_and_plan_lifecycle.sql` in `ArvaNet_Backend`.
  - [x] 1.2 Update backend entities (`ChatbotSession`, `PlantingPlan`, `PlantingTask`, `PlanStatusHistory`, `PlantingTaskDependency`, `PlanConversationLink`).
  - [x] 1.3 Add repositories for new and modified entities (`PlanConversationLinkRepository`, `PlanStatusHistoryRepository`, `PlantingTaskDependencyRepository`).

- [x] 2. **Backend API & Lifecycle Service**
  - [x] 2.1 Extend `FarmingChatbotService` with conversation history query, session archiving, and session resumption.
  - [x] 2.2 Implement plan lifecycle state transitions (`NOT_STARTED`, `IN_PROGRESS`, `CONTINUED`, `COMPLETED`, `CANCELLED`, `FAILED`) with audit history.
  - [x] 2.3 Implement task dependency management, cycle detection, blocked status checking, and automatic progress recalculation.
  - [x] 2.4 Expose new REST endpoints in `FarmingChatbotController`.

- [x] 3. **AI Chat Microservice Integration (ArvaAI)**
  - [x] 3.1 Enhance `ArvaMemoryStore` and `ArvaPersistentChatHistory` to support cross-conversation recall and plan linking.
  - [x] 3.2 Update `ArvaGeminiAdvisor` and models to consume previous conversation context and plan states.
  - [x] 3.3 Add endpoints in ArvaAI for conversation search and plan association (`/api/v1/ai/plans/register`, `/api/v1/ai/plans/active`, `/api/v1/ai/conversations/history`).

- [x] 4. **Frontend UI Components (ArvaNet_Frontend)**
  - [x] 4.1 Update models and DTOs in `farming_chat_models.dart`.
  - [x] 4.2 Add repository methods in `farming_chat_repository.dart` for conversations, plans, tasks, and lifecycle transitions.
  - [x] 4.3 Implement conversation history panel/drawer in `FarmingChatbotScreen`.
  - [x] 4.4 Implement Implementation Plan overview and Task dependency management controls in `FarmingChatbotScreen` and `ImplementationPlanDetailDialog`.

- [x] 5. **Testing & Verification**
  - [x] 5.1 Add unit and integration tests in `ArvaNet_Backend` (`FarmingChatbotServiceTest`, `PlanLifecycleAndDependencyTest` - 11/11 passed).
  - [x] 5.2 Add unit tests in `ArvaAI` (`test_plan_lifecycle.py` - 67/67 passed).
  - [x] 5.3 Verify Flutter compilation and unit tests (`farming_chat_models_test.dart` analyzed clean).
  - [x] 5.4 Validate OpenSpec change specification and archive.

- [ ] 6. **Deployment & Smoke Verification**
  - [ ] 6.1 Run `./scripts/redeploy-all.sh`.
  - [ ] 6.2 Execute backend and AI smoke tests.
  - [ ] 6.3 Verify endpoints and end-to-end functionality.
