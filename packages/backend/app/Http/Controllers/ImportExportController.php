<?php

namespace App\Http\Controllers;

use App\Http\Resources\TaskResource;
use App\Models\Task;
use App\Models\FormDefinition;
use App\Models\FormField;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class ImportExportController extends Controller
{
    /**
     * Export a task as JSON (without sensitive values).
     */
    public function export(Task $task): JsonResponse
    {
        if ($task->user_id !== request()->user()->id) {
            abort(403, 'Unauthorized access to this task.');
        }

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
}
