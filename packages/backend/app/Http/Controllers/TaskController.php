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

class TaskController extends Controller
{
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
            foreach ($validated['form_definitions'] as $fdData) {
                $fieldsData = $fdData['form_fields'] ?? [];
                unset($fdData['form_fields']);

                $fdData['task_id'] = $task->id;
                $formDefinition = FormDefinition::create($fdData);

                foreach ($fieldsData as $fieldData) {
                    $fieldData['form_definition_id'] = $formDefinition->id;

                    if (!empty($fieldData['is_sensitive']) && !empty($fieldData['preset_value'])) {
                        $fieldData['preset_value'] = app(CryptoService::class)->encrypt($fieldData['preset_value']);
                    }

                    FormField::create($fieldData);
                }
            }
        }

        $task->load('formDefinitions.formFields');

        return response()->json(new TaskResource($task), 201);
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

            foreach ($validated['form_definitions'] as $fdData) {
                $fieldsData = $fdData['form_fields'] ?? [];
                unset($fdData['form_fields']);

                $fdData['task_id'] = $task->id;
                $formDefinition = FormDefinition::create($fdData);

                foreach ($fieldsData as $fieldData) {
                    $fieldData['form_definition_id'] = $formDefinition->id;

                    if (!empty($fieldData['is_sensitive']) && !empty($fieldData['preset_value'])) {
                        $fieldData['preset_value'] = app(CryptoService::class)->encrypt($fieldData['preset_value']);
                    }

                    FormField::create($fieldData);
                }
            }
        }

        $task->load('formDefinitions.formFields');

        return new TaskResource($task);
    }

    /**
     * Remove the specified task.
     */
    public function destroy(Task $task): JsonResponse
    {
        $this->authorizeTask($task);
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

        return response()->json(new TaskResource($newTask), 201);
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
            foreach ($request->input('form_definitions') as $fdData) {
                $fieldsData = $fdData['form_fields'] ?? [];
                unset($fdData['form_fields'], $fdData['id'], $fdData['task_id'], $fdData['created_at'], $fdData['updated_at']);

                $fdData['task_id'] = $task->id;
                $formDefinition = FormDefinition::create($fdData);

                foreach ($fieldsData as $fieldData) {
                    unset($fieldData['id'], $fieldData['form_definition_id'], $fieldData['created_at'], $fieldData['updated_at']);
                    $fieldData['form_definition_id'] = $formDefinition->id;
                    FormField::create($fieldData);
                }
            }
        }

        $task->load('formDefinitions.formFields');

        return response()->json(new TaskResource($task), 201);
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
}
