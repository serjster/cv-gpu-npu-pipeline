# Facade Pattern

## Pattern Definition

The Facade Pattern provides a unified interface to a set of interfaces in a subsystem. Facade defines a higher-level interface that makes the subsystem easier to use.

**Keywords:** Structural, Simplification, Unified Interface, Decoupling

## Source Example

* [facade.h](examples/facade.h)

## Correct UML

```mermaid
classDiagram
    class Client
    class Facade {
        -subsystemA
        -subsystemB
        -subsystemC
        +operation()
    }
    class SubsystemA {
        +methodA()
    }
    class SubsystemB {
        +methodB()
    }
    class SubsystemC {
        +methodC()
    }
    Client --> Facade : uses
    Facade o-- SubsystemA : delegates to
    Facade o-- SubsystemB : delegates to
    Facade o-- SubsystemC : delegates to
```

## Bad UML #1

```mermaid
classDiagram
    %% Error: Client directly depends on all subsystems
    class Client
    class A
    class B
    class C
    class D
    Client --> A : uses
    Client --> B : uses
    Client --> C : uses
    Client --> D : uses
```

**What's wrong?** Client should depend on Facade, not directly on subsystems. The purpose of Facade is to simplify and decouple the client from subsystem complexity.

## Bad UML #2

```mermaid
classDiagram
    %% Error: Unnecessary interface
    class Client
    class FacadeInterface {
        <<interface>>
        +operation()
    }
    class ConcreteFacade {
        +operation()
    }
    Client --> FacadeInterface : uses
    FacadeInterface <|-- ConcreteFacade : implements
```

**What's wrong?** Facade is typically a concrete class, not an interface. Adding an interface adds unnecessary complexity unless you need multiple facades.

## Exercise Questions

* What's the difference between Facade and Adapter patterns?
* Can clients still access subsystems directly, or must they go through the Facade?
* How does Facade relate to the Law of Demeter?

## Interview Tips

* Understand that Facade simplifies, Adapter converts interfaces
* Know real-world examples (compiler facades, library wrappers, framework APIs)
* Discuss when to use Facade: complex subsystems, legacy code integration
* Explain that Facade doesn't prevent direct subsystem access (unlike complete encapsulation)
