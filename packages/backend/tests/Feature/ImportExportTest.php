<?php

namespace Tests\Feature;

use App\Models\FormDefinition;
use App\Models\FormField;
use App\Models\Task;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Passport\Passport;
use Tests\TestCase;

class ImportExportTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();

        $this->user = User::create([
            'name' => 'Test User',
            'email' => 'test@example.com',
            'password' => bcrypt('password123'),
        ]);

        Passport::actingAs($this->user);
    }

    private function createTaskWithForms(): Task
    {
        $task = Task::create([
            'user_id' => $this->user->id,
            'name' => 'Export Test Task',
            'target_url' => 'https://example.com/form',
            'status' => 'active',
            'schedule_type' => 'once',
            'max_retries' => 3,
            'stealth_enabled' => true,
            'action_delay_ms' => 500,
        ]);

        $fd = FormDefinition::create([
            'task_id' => $task->id,
            'step_order' => 1,
            'page_url' => 'https://example.com/login',
            'form_type' => 'login',
            'form_selector' => '#login-form',
            'submit_selector' => '#submit-btn',
        ]);

        FormField::create([
            'form_definition_id' => $fd->id,
            'field_name' => 'email',
            'field_type' => 'email',
            'field_selector' => '#email',
            'field_purpose' => 'email',
            'preset_value' => 'user@example.com',
            'is_sensitive' => false,
            'is_required' => true,
            'sort_order' => 0,
        ]);

        FormField::create([
            'form_definition_id' => $fd->id,
            'field_name' => 'password',
            'field_type' => 'password',
            'field_selector' => '#password',
            'field_purpose' => 'password',
            'preset_value' => 'supersecret',
            'is_sensitive' => true,
            'is_required' => true,
            'sort_order' => 1,
        ]);

        $fd2 = FormDefinition::create([
            'task_id' => $task->id,
            'step_order' => 2,
            'page_url' => 'https://example.com/target',
            'form_type' => 'target',
            'form_selector' => '#target-form',
            'submit_selector' => '#target-submit',
            'human_breakpoint' => true,
        ]);

        FormField::create([
            'form_definition_id' => $fd2->id,
            'field_name' => 'comment',
            'field_type' => 'textarea',
            'field_selector' => '#comment',
            'field_purpose' => 'comment',
            'preset_value' => 'Hello World',
            'is_sensitive' => false,
            'is_required' => false,
            'sort_order' => 0,
        ]);

        return $task;
    }

    // -----------------------------------------------------------------
    // Export task
    // -----------------------------------------------------------------

    public function test_export_task_returns_json_without_sensitive_data(): void
    {
        $task = $this->createTaskWithForms();

        // The route in api.php is POST /tasks/{task}/export via TaskController@export.
        $response = $this->postJson("/api/tasks/{$task->id}/export");

        $response->assertStatus(200);

        $data = $response->json();

        // Internal fields should be stripped
        $this->assertArrayNotHasKey('id', $data);
        $this->assertArrayNotHasKey('user_id', $data);
        $this->assertArrayNotHasKey('created_at', $data);
        $this->assertArrayNotHasKey('updated_at', $data);

        // Task data should be present
        $this->assertEquals('Export Test Task', $data['name']);
        $this->assertEquals('https://example.com/form', $data['target_url']);
        $this->assertEquals('active', $data['status']);

        // Form definitions should be present
        $this->assertCount(2, $data['form_definitions']);

        // First form definition (login)
        $loginFd = collect($data['form_definitions'])->firstWhere('form_type', 'login');
        $this->assertNotNull($loginFd);
        $this->assertEquals('#login-form', $loginFd['form_selector']);

        // Fields should exist
        $this->assertCount(2, $loginFd['form_fields']);

        // Sensitive field preset_value should be null
        $passwordField = collect($loginFd['form_fields'])->firstWhere('field_name', 'password');
        $this->assertTrue($passwordField['is_sensitive']);
        $this->assertNull($passwordField['preset_value']);

        // Non-sensitive field preset_value should be preserved
        $emailField = collect($loginFd['form_fields'])->firstWhere('field_name', 'email');
        $this->assertFalse($emailField['is_sensitive']);
        $this->assertEquals('user@example.com', $emailField['preset_value']);

        // Second form definition (target)
        $targetFd = collect($data['form_definitions'])->firstWhere('form_type', 'target');
        $this->assertNotNull($targetFd);
        $this->assertTrue($targetFd['human_breakpoint']);
        $this->assertCount(1, $targetFd['form_fields']);
    }

    public function test_export_task_of_another_user_returns_403(): void
    {
        $otherUser = User::create([
            'name' => 'Other',
            'email' => 'other@example.com',
            'password' => bcrypt('password'),
        ]);

        $otherTask = Task::create([
            'user_id' => $otherUser->id,
            'name' => 'Other Task',
            'target_url' => 'https://other.com',
            'status' => 'draft',
        ]);

        $response = $this->postJson("/api/tasks/{$otherTask->id}/export");

        $response->assertStatus(403);
    }

    // -----------------------------------------------------------------
    // Import task
    // -----------------------------------------------------------------

    public function test_import_task_creates_new_task_in_draft_status(): void
    {
        $response = $this->postJson('/api/tasks/import', [
            'name' => 'Imported Task',
            'target_url' => 'https://imported.com/form',
            'schedule_type' => 'once',
            'max_retries' => 5,
            'stealth_enabled' => true,
            'form_definitions' => [
                [
                    'step_order' => 1,
                    'page_url' => 'https://imported.com/login',
                    'form_type' => 'login',
                    'form_selector' => '#form',
                    'submit_selector' => '#submit',
                    'form_fields' => [
                        [
                            'field_name' => 'username',
                            'field_type' => 'text',
                            'field_selector' => '#username',
                            'field_purpose' => 'username',
                            'preset_value' => 'importeduser',
                            'is_sensitive' => false,
                            'is_required' => true,
                            'sort_order' => 0,
                        ],
                    ],
                ],
            ],
        ]);

        $response->assertStatus(201);

        $data = $response->json('data');

        // Status should be forced to draft regardless of input
        $this->assertEquals('draft', $data['status']);

        // Should belong to the authenticated user
        $this->assertEquals($this->user->id, $data['user_id']);

        // Task name preserved
        $this->assertEquals('Imported Task', $data['name']);
        $this->assertEquals('https://imported.com/form', $data['target_url']);

        // Form definitions imported
        $this->assertCount(1, $data['form_definitions']);
        $this->assertEquals('login', $data['form_definitions'][0]['form_type']);

        // Fields imported
        $this->assertCount(1, $data['form_definitions'][0]['form_fields']);
        $this->assertEquals('username', $data['form_definitions'][0]['form_fields'][0]['field_name']);

        // Verify database persistence
        $this->assertDatabaseHas('tasks', [
            'name' => 'Imported Task',
            'status' => 'draft',
            'user_id' => $this->user->id,
        ]);
        $this->assertDatabaseHas('form_definitions', [
            'form_type' => 'login',
            'form_selector' => '#form',
        ]);
        $this->assertDatabaseHas('form_fields', [
            'field_name' => 'username',
            'preset_value' => 'importeduser',
        ]);
    }

    public function test_import_task_without_form_definitions(): void
    {
        $response = $this->postJson('/api/tasks/import', [
            'name' => 'Simple Import',
            'target_url' => 'https://simple.com',
        ]);

        $response->assertStatus(201)
            ->assertJsonPath('data.name', 'Simple Import')
            ->assertJsonPath('data.status', 'draft');

        // No form definitions should be created
        $taskId = $response->json('data.id');
        $this->assertEquals(0, FormDefinition::where('task_id', $taskId)->count());
    }

    public function test_import_task_validation_requires_name_and_url(): void
    {
        $response = $this->postJson('/api/tasks/import', []);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['name', 'target_url']);
    }

    public function test_import_task_validation_requires_valid_url(): void
    {
        $response = $this->postJson('/api/tasks/import', [
            'name' => 'Bad Import',
            'target_url' => 'not-a-url',
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['target_url']);
    }

    public function test_import_strips_internal_ids_from_input(): void
    {
        // When importing, old IDs in form_definitions and form_fields should be ignored.
        // New IDs should be generated.
        $response = $this->postJson('/api/tasks/import', [
            'name' => 'Import With IDs',
            'target_url' => 'https://example.com',
            'form_definitions' => [
                [
                    'id' => '00000000-0000-0000-0000-111111111111',
                    'task_id' => '00000000-0000-0000-0000-222222222222',
                    'step_order' => 1,
                    'page_url' => 'https://example.com',
                    'form_type' => 'target',
                    'form_selector' => '#form',
                    'submit_selector' => '#submit',
                    'form_fields' => [
                        [
                            'id' => '00000000-0000-0000-0000-333333333333',
                            'form_definition_id' => '00000000-0000-0000-0000-111111111111',
                            'field_name' => 'test',
                            'field_type' => 'text',
                            'field_selector' => '#test',
                            'sort_order' => 0,
                        ],
                    ],
                ],
            ],
        ]);

        $response->assertStatus(201);

        $data = $response->json('data');

        // IDs should be newly generated, not the ones we passed in
        $this->assertNotEquals('00000000-0000-0000-0000-111111111111', $data['form_definitions'][0]['id']);
        $this->assertNotEquals('00000000-0000-0000-0000-333333333333', $data['form_definitions'][0]['form_fields'][0]['id']);

        // The form definition should reference the newly created task
        $fdTaskId = FormDefinition::first()->task_id;
        $this->assertEquals($data['id'], $fdTaskId);
    }

    // -----------------------------------------------------------------
    // Round-trip: export then import
    // -----------------------------------------------------------------

    public function test_export_then_import_round_trip(): void
    {
        $originalTask = $this->createTaskWithForms();

        // Export
        $exportResponse = $this->postJson("/api/tasks/{$originalTask->id}/export");
        $exportResponse->assertStatus(200);
        $exportedData = $exportResponse->json();

        // Import the exported data
        $importResponse = $this->postJson('/api/tasks/import', $exportedData);
        $importResponse->assertStatus(201);

        $importedData = $importResponse->json('data');

        // The imported task should match the original in key attributes
        $this->assertEquals($exportedData['name'], $importedData['name']);
        $this->assertEquals($exportedData['target_url'], $importedData['target_url']);

        // But it should be a new task in draft status
        $this->assertNotEquals($originalTask->id, $importedData['id']);
        $this->assertEquals('draft', $importedData['status']);

        // Form definitions should be recreated
        $this->assertCount(
            count($exportedData['form_definitions']),
            $importedData['form_definitions']
        );
    }
}
