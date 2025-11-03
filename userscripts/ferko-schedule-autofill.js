// ==UserScript==
// @name         Ferko schedule auto-fill
// @namespace    Ivan1248
// @version      1.0
// @description  Automatically fill schedule entries in Ferko
// @author       Past light cone
// @match        https://ferko.fer.hr/ferko/CCIManager!editGroupOwners.action*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // Parse schedule input
    function parseSchedule(input) {
        const events = [];
        const lines = input.trim().split('\n');

        for (const line of lines) {
            if (!line.trim()) continue;

            // Split by tab to handle multiple entries per line
            const entries = line.split('\t').filter(e => e.trim());

            for (let i = 0; i < entries.length; i++) {
                const entry = entries[i].trim();
                // Match pattern: YYYY-MM-DD|HH:MM|HH:MM|ROOM
                const match = entry.match(/^(\d{4}-\d{2}-\d{2})\|(\d{2}:\d{2})\|(\d{2}:\d{2})\|(A-?\d+)/);

                if (match && i + 1 < entries.length) {
                    const name = entries[i + 1].trim();
                    if (name && !name.match(/^\d{4}-\d{2}-\d{2}/)) {
                        events.push({
                            date: match[1],
                            startTime: match[2],
                            endTime: match[3],
                            room: match[4].replace('-', ''), // Remove dash from room
                            name: name
                        });
                        i++; // Skip next entry as it's the name
                    }
                }
            }
        }

        return events;
    }

    // Find matching div for a schedule event
    function findMatchingDiv(event) {
        const editor = document.getElementById('editor');
        if (!editor) return null;

        const divs = editor.querySelectorAll('div');

        for (const div of divs) {
            const text = div.textContent;
            // Match format: YYYY-MM-DD HH:MM HH:MM AROOM
            const pattern = `${event.date} ${event.startTime} ${event.endTime} ${event.room}`;

            if (text.includes(pattern)) {
                const dodajSpan = div.querySelector('span.ui-icon-plusthick');
                if (dodajSpan) {
                    return dodajSpan;
                }
            }
        }

        return null;
    }

    // Check if person is already assigned to a slot
    function isPersonAlreadyAssigned(dodajSpan, name) {
        // Get the parent div of the dodaj button
        const parentDiv = dodajSpan.closest('div');
        if (!parentDiv) return false;

        // Find the next sibling div that contains the ul with assigned people
        let nextDiv = parentDiv.nextElementSibling;
        while (nextDiv) {
            const ul = nextDiv.querySelector('ul[id^="ul_"]');
            if (ul) {
                // Check if any li contains the person's name
                const lis = ul.querySelectorAll('li');
                for (const li of lis) {
                    const text = li.textContent;
                    const nameParts = name.split(' ');

                    if (nameParts.length >= 2) {
                        const lastName = nameParts[nameParts.length - 1];
                        const firstName = nameParts[0];

                        if (text.includes(lastName) && text.includes(firstName)) {
                            return true;
                        }
                    } else if (text.includes(name)) {
                        return true;
                    }
                }
                break;
            }
            nextDiv = nextDiv.nextElementSibling;
        }

        return false;
    }

    function findPersonInDialog(name) {
        const dialog = document.getElementById('editorDialog');
        if (!dialog) return null;

        const divs = dialog.querySelectorAll('div[onclick^="dodajKorGrupa"]');

        for (const div of divs) {
            const text = div.textContent;
            // Check if the name matches (last name, first name format)
            const nameParts = name.split(' ');
            if (nameParts.length >= 2) {
                const lastName = nameParts[nameParts.length - 1];
                const firstName = nameParts[0];

                if (text.includes(lastName) && text.includes(firstName)) {
                    return div;
                }
            } else if (text.includes(name)) {
                return div;
            }
        }

        return null;
    }

    // Wait for dialog to appear
    function waitForDialog(timeout = 5000) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();

            const checkDialog = setInterval(() => {
                const dialog = document.getElementById('editorDialog');
                if (dialog && dialog.style.display !== 'none') {
                    clearInterval(checkDialog);
                    resolve(dialog);
                }

                if (Date.now() - startTime > timeout) {
                    clearInterval(checkDialog);
                    reject(new Error('Dialog timeout'));
                }
            }, 100);
        });
    }

    // Wait for dialog to close
    function waitForDialogClose(timeout = 5000) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();

            const checkDialog = setInterval(() => {
                const dialog = document.getElementById('editorDialog');
                if (!dialog) {
                    clearInterval(checkDialog);
                    resolve();
                    return;
                }

                // Check if parent element (the actual dialog wrapper) is hidden
                const parentDialog = dialog.closest('.ui-dialog');
                if (parentDialog && parentDialog.style.display === 'none') {
                    clearInterval(checkDialog);
                    resolve();
                    return;
                }

                // Fallback: check if dialog itself is hidden
                if (dialog.style.display === 'none') {
                    clearInterval(checkDialog);
                    resolve();
                    return;
                }

                if (Date.now() - startTime > timeout) {
                    clearInterval(checkDialog);
                    reject(new Error('Dialog close timeout'));
                }
            }, 100);
        });
    }

    // Process events one by one
    async function processEvents(events) {
        console.log(`Processing ${events.length} events...`);

        const results = {
            success: [],
            alreadyAssigned: [],
            slotNotFound: [],
            personNotFound: [],
            errors: []
        };

        for (let i = 0; i < events.length; i++) {
            const event = events[i];
            const eventStr = `${event.date} ${event.startTime}-${event.endTime} ${event.room} - ${event.name}`;
            console.log(`[${i+1}/${events.length}] Processing: ${eventStr}`);

            // Find and click the dodaj button
            const dodajBtn = findMatchingDiv(event);
            if (!dodajBtn) {
                console.warn(`  ⚠ Could not find matching slot`);
                results.slotNotFound.push(eventStr);
                continue;
            }

            // Check if person is already assigned
            if (isPersonAlreadyAssigned(dodajBtn, event.name)) {
                console.log(`  ℹ Person already assigned, skipping`);
                results.alreadyAssigned.push(eventStr);
                continue;
            }

            dodajBtn.click();
            console.log(`  ✓ Clicked dodaj button`);

            try {
                // Wait for dialog to open
                await waitForDialog();
                console.log(`  ✓ Dialog opened`);

                // Find and click the person
                await new Promise(resolve => setTimeout(resolve, 300)); // Small delay for dialog to fully render
                const personDiv = findPersonInDialog(event.name);

                if (!personDiv) {
                    console.warn(`  ⚠ Could not find person: ${event.name}`);
                    results.personNotFound.push(eventStr);
                    // Try to close dialog
                    const closeBtn = document.querySelector('#editorDialog .ui-dialog-titlebar-close');
                    if (closeBtn) closeBtn.click();
                    await new Promise(resolve => setTimeout(resolve, 300));
                    continue;
                }

                personDiv.click();
                console.log(`  ✓ Selected person: ${event.name}`);

                // Wait for dialog to close
                await waitForDialogClose();
                console.log(`  ✓ Dialog closed`);

                results.success.push(eventStr);

                // Delay before next iteration
                await new Promise(resolve => setTimeout(resolve, 500));

            } catch (error) {
                console.error(`  ✗ Error: ${error.message}`);
                results.errors.push({event: eventStr, error: error.message});
            }
        }

        console.log('✓ All events processed!');
        return results;
    }

    // Add UI
    function createUI() {
        const container = document.createElement('div');
        container.id = 'scheduleAutoFillUI';
        container.style.cssText = `
            position: fixed;
            top: 60px;
            right: 10px;
            background: white;
            border: 2px solid #333;
            padding: 10px;
            z-index: 10000;
            max-width: 400px;
            box-sizing: border-box;
        `;

        container.innerHTML = `
            <h3 style="margin: 0 0 5px 0;">Schedule auto-fill</h3>
            <textarea id="scheduleInput" placeholder="Paste schedule here..." style="width: 100%; height: 150px; margin-bottom: 5px; font-family: monospace; font-size: 11px; box-sizing: border-box;"></textarea>
            <div style="display: flex; gap: 5px;">
                <button id="processBtn" style="flex: 1; padding: 5px; background: #4CAF50; color: white; border: none; border-radius: 0px; font-weight: bold;">Process schedule</button>
                <button id="toggleBtn" style="flex: 0 0 auto; padding: 5px 15px; background: #666; color: white; border: none; border-radius: 0px;">Minimize</button>
            </div>
        `;

        document.body.appendChild(container);

        const processBtn = document.getElementById('processBtn');
        const scheduleInput = document.getElementById('scheduleInput');
        const toggleBtn = document.getElementById('toggleBtn');

        let minimized = false;

        toggleBtn.addEventListener('click', () => {
            minimized = !minimized;
            if (minimized) {
                scheduleInput.style.display = 'none';
                processBtn.style.display = 'none';
                toggleBtn.textContent = 'Show';
                container.style.width = 'auto';
            } else {
                scheduleInput.style.display = 'block';
                processBtn.style.display = 'block';
                toggleBtn.textContent = 'Minimize';
                container.style.width = '';
            }
        });

        processBtn.addEventListener('click', async () => {
            const input = scheduleInput.value;
            if (!input.trim()) {
                alert('Please paste schedule data first!');
                return;
            }

            const events = parseSchedule(input);
            if (events.length === 0) {
                alert('No valid events found in input!');
                return;
            }

            processBtn.disabled = true;
            processBtn.textContent = `Processing ${events.length} events...`;

            try {
                const results = await processEvents(events);

                // Generate report
                let report = `Processing Complete!\n\n`;
                report += `✓ Successfully processed: ${results.success.length}\n`;
                report += `ℹ Already assigned (skipped): ${results.alreadyAssigned.length}\n`;

                if (results.slotNotFound.length > 0) {
                    report += `\n⚠ Slot not found (${results.slotNotFound.length}):\n`;
                    results.slotNotFound.forEach(e => report += `  - ${e}\n`);
                }

                if (results.personNotFound.length > 0) {
                    report += `\n⚠ Person not found in list (${results.personNotFound.length}):\n`;
                    results.personNotFound.forEach(e => report += `  - ${e}\n`);
                }

                if (results.errors.length > 0) {
                    report += `\n✗ Errors (${results.errors.length}):\n`;
                    results.errors.forEach(e => report += `  - ${e.event}: ${e.error}\n`);
                }

                alert(report);
                console.log('\n' + report);
            } catch (error) {
                alert('Error processing schedule: ' + error.message);
            } finally {
                processBtn.disabled = false;
                processBtn.textContent = 'Process Schedule';
            }
        });
    }

    // Initialize
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createUI);
    } else {
        createUI();
    }
})();