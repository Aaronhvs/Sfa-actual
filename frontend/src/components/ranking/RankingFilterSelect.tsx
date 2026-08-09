import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'

export interface RankingFilterOption {
  value: string
  label: string
}

interface Props {
  label: string
  ariaLabel: string
  value: string
  options: RankingFilterOption[]
  onChange: (value: string) => void
}

export default function RankingFilterSelect({
  label,
  ariaLabel,
  value,
  options,
  onChange,
}: Props) {
  const menuId = useId()
  const wrapperRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([])
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value))
  const [open, setOpen] = useState(false)
  const [highlightedIndex, setHighlightedIndex] = useState(selectedIndex)

  useEffect(() => {
    if (!open) return

    const closeOnOutsidePress = (event: PointerEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false)
    }

    document.addEventListener('pointerdown', closeOnOutsidePress)
    return () => document.removeEventListener('pointerdown', closeOnOutsidePress)
  }, [open])

  useEffect(() => {
    if (!open) return
    setHighlightedIndex(selectedIndex)
  }, [open, selectedIndex])

  const closeMenu = (returnFocus = false) => {
    setOpen(false)
    if (returnFocus) requestAnimationFrame(() => triggerRef.current?.focus())
  }

  const openMenu = (index = selectedIndex, focusOption = false) => {
    setHighlightedIndex(index)
    setOpen(true)
    if (focusOption) requestAnimationFrame(() => optionRefs.current[index]?.focus())
  }

  const moveHighlight = (index: number) => {
    const nextIndex = (index + options.length) % options.length
    setHighlightedIndex(nextIndex)
    optionRefs.current[nextIndex]?.focus()
  }

  const selectOption = (index: number) => {
    onChange(options[index].value)
    closeMenu(true)
  }

  const handleTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      const nextIndex = open
        ? (highlightedIndex + 1) % options.length
        : selectedIndex
      openMenu(nextIndex, true)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      const nextIndex = open
        ? (highlightedIndex - 1 + options.length) % options.length
        : selectedIndex
      openMenu(nextIndex, true)
    } else if (event.key === 'Home') {
      event.preventDefault()
      openMenu(0, true)
    } else if (event.key === 'End') {
      event.preventDefault()
      openMenu(options.length - 1, true)
    } else if (event.key === 'Escape' && open) {
      event.preventDefault()
      closeMenu()
    }
  }

  const handleOptionKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      moveHighlight(index + 1)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      moveHighlight(index - 1)
    } else if (event.key === 'Home') {
      event.preventDefault()
      moveHighlight(0)
    } else if (event.key === 'End') {
      event.preventDefault()
      moveHighlight(options.length - 1)
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      selectOption(index)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      closeMenu(true)
    } else if (event.key === 'Tab') {
      closeMenu()
    } else if (event.key.length === 1) {
      const query = event.key.toLocaleLowerCase()
      const match = options.findIndex((option, optionIndex) => (
        optionIndex !== index && option.label.toLocaleLowerCase().startsWith(query)
      ))
      if (match >= 0) {
        event.preventDefault()
        moveHighlight(match)
      }
    }
  }

  const selectedOption = options[selectedIndex]

  return (
    <div
      ref={wrapperRef}
      className={`filter-select${value ? ' filter-select--active' : ''}${open ? ' filter-select--open' : ''}`}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) closeMenu()
      }}
    >
      <button
        ref={triggerRef}
        type="button"
        className="filter-select__face"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => (open ? closeMenu() : openMenu())}
        onKeyDown={handleTriggerKeyDown}
      >
        <span className="filter-select__label">{label}</span>
        <span className="filter-select__value">{selectedOption.label}</span>
      </button>

      <div
        id={menuId}
        className={`filter-select__menu${open ? ' filter-select__menu--open' : ''}`}
        role="listbox"
        aria-label={ariaLabel}
        aria-hidden={!open}
        style={{ '--filter-option-index': highlightedIndex } as React.CSSProperties}
      >
        <span className="filter-select__glider" aria-hidden="true" />
        {options.map((option, index) => (
          <button
            key={option.value || 'all'}
            ref={(element) => { optionRefs.current[index] = element }}
            type="button"
            className="filter-select__option"
            role="option"
            aria-selected={option.value === value}
            tabIndex={open && index === highlightedIndex ? 0 : -1}
            onClick={() => selectOption(index)}
            onFocus={() => setHighlightedIndex(index)}
            onMouseEnter={() => setHighlightedIndex(index)}
            onKeyDown={(event) => handleOptionKeyDown(event, index)}
          >
            <span className="filter-select__indicator" aria-hidden="true" />
            <span className="filter-select__option-label">{option.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
