# Decorator Pattern

## Pattern Definition

The Decorator Pattern attaches additional responsibilities to an object dynamically. Decorators provide a flexible alternative to subclassing for extending functionality.

**Keywords:** Structural, Dynamic Behavior, Wrapper, Composition

## Source Example

* [decorator.h](examples/decorator.h)

## Correct UML

```mermaid
classDiagram
    class Component {
        <<abstract>>
        +operation()
    }
    class ConcreteComponent {
        +operation()
    }
    class Decorator {
        <<abstract>>
        -component
        +operation()
    }
    class ConcreteDecorator {
        +operation()
        +addedBehavior()
    }
    Component <|-- ConcreteComponent : extends
    Component <|-- Decorator : extends
    Decorator <|-- ConcreteDecorator : extends
    Decorator *-- Component : wraps
```

## Bad UML #1

```mermaid
classDiagram
    class Component {
        +operation()
    }
    class ConcreteComponent {
        +operation()
    }
    class ConcreteDecorator {
        +operation()
    }
    Component <|-- ConcreteComponent : extends
    ConcreteComponent <|-- ConcreteDecorator : extends
    %% Error: Decorator shouldn't inherit from ConcreteComponent
```

**What's wrong?** Decorator should inherit from Component (the interface), not from ConcreteComponent. This allows decorators to wrap any component, not just concrete ones.

## Bad UML #2

```mermaid
classDiagram
    class Component {
        +operation()
    }
    class Decorator {
        +operation()
    }
    class ConcreteComponent {
        +operation()
    }
    class ConcreteDecorator {
        +operation()
    }
    Component <|-- ConcreteComponent : extends
    Component <-- Decorator : uses
    Decorator <|-- ConcreteDecorator : extends
    %% Error: No composition relationship between Decorator and Component
```

**What's wrong?** Missing the composition relationship between Decorator and Component. Decorators must hold a reference to the component they're decorating.

## Exercise Questions

* How does Decorator differ from inheritance for extending functionality?
* What are the downsides of using many decorators?
* How does Decorator relate to the Open/Closed Principle?

## Interview Tips

* Understand the difference between Decorator and Proxy patterns
* Know real-world examples (Java I/O streams, UI component wrapping)
* Discuss issues: ordering of decorators, type identification
* Be ready to explain why composition is preferred over inheritance here
