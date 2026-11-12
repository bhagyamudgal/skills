# When generate stops on a prompt

drizzle-kit asks "created or renamed?" whenever a diff drops one column or table and adds another, and an agent shell has no TTY to answer it. When generate errors on a prompt or TTY, or hits the two-minute limit, stop and hand the user:

- the generate command without the `/dev/null` redirect or the time limit, so they can answer, to run in their own terminal from the config's generate directory;
- the answer for each prompt, read from the stale SQL. A `RENAME` statement there means "renamed", and a matching `DROP` with `ADD` means "created".

Resume at step 5 once the user reports the new files exist.
