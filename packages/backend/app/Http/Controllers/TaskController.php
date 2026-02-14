<?php

namespace App\Http\Controllers;

use App\Events\TaskStatusChanged;
use App\Http\Requests\StoreTaskRequest;
use App\Http\Requests\UpdateTaskRequest;
use App\Http\Resources\TaskResource;
use App\Jobs\ExecuteTaskJob;
use App\Models\Task;
use App\Models\FormDefinition;
use App\Models\FormField;
use App\Services\CryptoService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Validation\ValidationException;

class TaskController extends Controller
{
    private const FORM_DEFINITION_KEYS = [
        'step_order',
        'depends_on_step_order',
        'page_url',
        'form_type',
        'form_selector',
        'submit_selector',
        'human_breakpoint',
    ];

    private const FORM_FIELD_KEYS = [
        'field_name',
        'field_type',
        'field_selector',
        'field_purpose',
        'preset_value',
        'is_sensitive',
        'is_file_upload',
        'is_required',
        'options',
        'sort_order',
    ];

    /**
     * Display a listing of the user's tasks.
     */
    public function index(Request $request): AnonymousResourceCollection
    {
        $query = $request->user()->tasks()->with('formDefinitions.formFields');

        if ($request->has('status')) {
            $query->where('status', $request->input('status'));
        }

        if ($request->has('search')) {
            $search = $request->input('search');
            $query->where(function ($q) use ($search) {
                $q->where('name', 'ilike', "%{$search}%")
                  ->orWhere('target_url', 'ilike', "%{$search}%");
            });
        }

        $tasks = $query->orderBy('updated_at', 'desc')->paginate(
            $request->input('per_page', 15)
        );

        return TaskResource::collection($tasks);
    }

    /**
     * Store a newly created task.
     */
    public function store(StoreTaskRequest $request): JsonResponse
    {
        $validated = $request->validated();

        $taskData = collect($validated)->except('form_definitions')->toArray();
        $taskData['user_id'] = $request->user()->id;

        $task = Task::create($taskData);

        if (!empty($validated['form_definitions'])) {
            $this->persistFormDefinitions($task, $validated['form_definitions']);
        }

        $task->load('formDefinitions.formFields');

        event(new TaskStatusChanged($task));

        return (new TaskResource($task))->response()->setStatusCode(201);
    }

    /**
     * Display the specified task.
     */
    public function show(Task $task): TaskResource
    {
        $this->authorizeTask($task);
        $task->load('formDefinitions.formFields');

        return new TaskResource($task);
    }

    /**
     * Update the specified task.
     */
    public function update(UpdateTaskRequest $request, Task $task): TaskResource
    {
        $this->authorizeTask($task);
        $validated = $request->validated();

        $taskData = collect($validated)->except('form_definitions')->toArray();
        $task->update($taskData);

        if (isset($validated['form_definitions'])) {
            // Delete existing form definitions (cascade deletes fields)
            $task->formDefinitions()->delete();
            $this->persistFormDefinitions($task, $validated['form_definitions']);
        }

        $task->load('formDefinitions.formFields');

        event(new TaskStatusChanged($task));

        return new TaskResource($task);
    }

    /**
     * Remove the specified task.
     */
    public function destroy(Task $task): JsonResponse
    {
        $this->authorizeTask($task);

        $task->status = 'deleted';
        event(new TaskStatusChanged($task));

        $task->delete();

        return response()->json(['message' => 'Task deleted successfully.']);
    }

    /**
     * Clone a task.
     */
    public function clone(Task $task): JsonResponse
    {
        $this->authorizeTask($task);
        $task->load('formDefinitions.formFields');

        $newTask = $task->replicate(['id']);
        $newTask->name = $task->name . ' (Copy)';
        $newTask->status = 'draft';
        $newTask->cloned_from = $task->id;
        $newTask->login_session_data = null; // Never copy session data
        $newTask->save();

        foreach ($task->formDefinitions as $fd) {
            $newFd = $fd->replicate(['id']);
            $newFd->task_id = $newTask->id;
            $newFd->save();

            foreach ($fd->formFields as $field) {
                $newField = $field->replicate(['id']);
                $newField->form_definition_id = $newFd->id;

                // Clear sensitive values
                if ($field->is_sensitive) {
                    $newField->preset_value = null;
                }

                $newField->save();
            }
        }

        $newTask->load('formDefinitions.formFields');

        event(new TaskStatusChanged($newTask));

        return (new TaskResource($newTask))->response()->setStatusCode(201);
    }

    /**
     * Activate a task.
     */
    public function activate(Task $task): TaskResource
    {
        $this->authorizeTask($task);
        $task->update(['status' => 'active']);

        event(new TaskStatusChanged($task));

        return new TaskResource($task);
    }

    /**
     * Pause a task.
     */
    public function pause(Task $task): TaskResource
    {
        $this->authorizeTask($task);
        $task->update(['status' => 'paused']);

        event(new TaskStatusChanged($task));

        return new TaskResource($task);
    }

    /**
     * Execute a task immediately.
     */
    public function execute(Task $task): JsonResponse
    {
        $this->authorizeTask($task);

        ExecuteTaskJob::dispatch($task, false);

        event(new TaskStatusChanged($task));

        return response()->json(['message' => 'Task execution queued.']);
    }

    /**
     * Execute a dry run of the task.
     */
    public function dryRun(Task $task): JsonResponse
    {
        $this->authorizeTask($task);

        ExecuteTaskJob::dispatch($task, true);

        return response()->json(['message' => 'Dry run execution queued.']);
    }

    /**
     * Export a task as JSON (without sensitive values).
     */
    public function export(Task $task): JsonResponse
    {
        $this->authorizeTask($task);
        $task->load('formDefinitions.formFields');

        $data = $task->toArray();

        // Remove sensitive field values
        if (!empty($data['form_definitions'])) {
            foreach ($data['form_definitions'] as &$fd) {
                if (!empty($fd['form_fields'])) {
                    foreach ($fd['form_fields'] as &$field) {
                        if ($field['is_sensitive']) {
                            $field['preset_value'] = null;
                        }
                    }
                }
            }
        }

        // Remove internal fields
        unset($data['id'], $data['user_id'], $data['created_at'], $data['updated_at']);

        return response()->json($data);
    }

    /**
     * Import a task from JSON.
     */
    public function import(Request $request): JsonResponse
    {
        $request->validate([
            'name' => ['required', 'string', 'max:255'],
            'target_url' => ['required', 'url'],
        ]);

        $taskData = $request->except(['form_definitions']);
        $taskData['user_id'] = $request->user()->id;
        $taskData['status'] = 'draft';

        $task = Task::create($taskData);

        if ($request->has('form_definitions')) {
            $formDefinitions = $request->input('form_definitions', []);
            if (is_array($formDefinitions)) {
                $this->persistFormDefinitions($task, $formDefinitions);
            }
        }

        $task->load('formDefinitions.formFields');

        return (new TaskResource($task))->response()->setStatusCode(201);
    }

    /**
     * Authorize that the authenticated user owns the task.
     */
    private function authorizeTask(Task $task): void
    {
        if ($task->user_id !== request()->user()->id) {
            abort(403, 'Unauthorized access to this task.');
        }
    }

    /**
     * Persist form definitions/fields while dropping unknown payload keys.
     */
    private function persistFormDefinitions(Task $task, array $formDefinitions): void
    {
        $normalized = [];

        foreach ($formDefinitions as $index => $fdData) {
            if (!is_array($fdData)) {
                continue;
            }

            $fieldsData = is_array($fdData['form_fields'] ?? null) ? $fdData['form_fields'] : [];
            $sanitizedDefinition = $this->sanitizeFormDefinitionData($fdData, $task->id, $index);

            $normalized[] = [
                'definition' => $sanitizedDefinition,
                'fields' => $fieldsData,
            ];
        }

        $this->validateFormDefinitionGraph(array_column($normalized, 'definition'));

        foreach ($normalized as $entry) {
            $formDefinition = FormDefinition::create($entry['definition']);
            $this->persistFormFields($formDefinition, $entry['fields']);
        }
    }

    private function persistFormFields(FormDefinition $formDefinition, array $fieldsData): void
    {
        foreach ($fieldsData as $fieldData) {
            $sanitizedField = $this->sanitizeFormFieldData((array) $fieldData, $formDefinition->id);

            if (!empty($sanitizedField['is_sensitive']) && !empty($sanitizedField['preset_value'])) {
                $sanitizedField['preset_value'] = app(CryptoService::class)->encrypt($sanitizedField['preset_value']);
            }

            FormField::create($sanitizedField);
        }
    }

    private function sanitizeFormDefinitionData(array $fdData, string $taskId, int $fallbackStepOrder): array
    {
        $sanitized = collect($fdData)->only(self::FORM_DEFINITION_KEYS)->toArray();
        $sanitized['task_id'] = $taskId;
        $sanitized['step_order'] = (int) ($sanitized['step_order'] ?? $fallbackStepOrder);

        if (
            !array_key_exists('depends_on_step_order', $sanitized)
            || $sanitized['depends_on_step_order'] === ''
            || $sanitized['depends_on_step_order'] === null
        ) {
            $sanitized['depends_on_step_order'] = null;
        } else {
            $sanitized['depends_on_step_order'] = (int) $sanitized['depends_on_step_order'];
        }

        return $sanitized;
    }

    private function validateFormDefinitionGraph(array $definitions): void
    {
        if ($definitions === []) {
            return;
        }

        $errors = [];
        $stepToIndex = [];
        $dependencyByStep = [];

        foreach ($definitions as $index => $definition) {
            $stepOrder = $definition['step_order'];
            $dependency = $definition['depends_on_step_order'];

            if (isset($stepToIndex[$stepOrder])) {
                $errors["form_definitions.{$index}.step_order"][] = 'step_order must be unique.';
                continue;
            }

            $stepToIndex[$stepOrder] = $index;

            if ($dependency === null) {
                $dependencyByStep[$stepOrder] = null;
                continue;
            }

            if ($dependency === $stepOrder) {
                $errors["form_definitions.{$index}.depends_on_step_order"][] = 'A step cannot depend on itself.';
            }

            $dependencyByStep[$stepOrder] = $dependency;
        }

        foreach ($dependencyByStep as $stepOrder => $dependency) {
            if ($dependency === null) {
                continue;
            }

            if (!array_key_exists($dependency, $stepToIndex)) {
                $index = $stepToIndex[$stepOrder] ?? 0;
                $errors["form_definitions.{$index}.depends_on_step_order"][] = 'depends_on_step_order must match an existing step_order.';
            }
        }

        if ($errors === [] && $this->hasDependencyCycle($dependencyByStep)) {
            $errors['form_definitions'][] = 'Step dependencies contain a cycle.';
        }

        if ($errors !== []) {
            throw ValidationException::withMessages($errors);
        }
    }

    private function hasDependencyCycle(array $dependencyByStep): bool
    {
        $visited = [];
        $visiting = [];

        foreach (array_keys($dependencyByStep) as $stepOrder) {
            if ($this->visitDependencyNode($stepOrder, $dependencyByStep, $visiting, $visited)) {
                return true;
            }
        }

        return false;
    }

    private function visitDependencyNode(
        int $stepOrder,
        array $dependencyByStep,
        array &$visiting,
        array &$visited,
    ): bool {
        if (!empty($visiting[$stepOrder])) {
            return true;
        }

        if (!empty($visited[$stepOrder])) {
            return false;
        }

        $visiting[$stepOrder] = true;
        $dependency = $dependencyByStep[$stepOrder] ?? null;

        if ($dependency !== null && $this->visitDependencyNode($dependency, $dependencyByStep, $visiting, $visited)) {
            return true;
        }

        unset($visiting[$stepOrder]);
        $visited[$stepOrder] = true;

        return false;
    }

    private function sanitizeFormFieldData(array $fieldData, string $formDefinitionId): array
    {
        $sanitized = collect($fieldData)->only(self::FORM_FIELD_KEYS)->toArray();
        $sanitized['form_definition_id'] = $formDefinitionId;

        return $sanitized;
    }
}
