"""Remove unused fictional demo venues from the configured database."""

import logic


def main():
    """Remove eligible demo venues and print each deleted name."""
    deleted = logic.remove_demo_venues()
    if not deleted:
        print("No eligible demo venues were deleted.")
        return
    for name in deleted:
        print(f"Deleted: {name}")


if __name__ == "__main__":
    main()
