import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

public class JavaPracticeTemplate {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        System.out.println("Java practice template");
        System.out.print("Enter your name: ");
        String name = scanner.nextLine();

        List<String> topics = new ArrayList<>();
        topics.add("variables");
        topics.add("conditionals");
        topics.add("loops");
        topics.add("methods");
        topics.add("collections");

        greet(name);
        printTopics(topics);

        scanner.close();
    }

    private static void greet(String name) {
        if (name == null || name.isBlank()) {
            System.out.println("Hello, learner!");
        } else {
            System.out.println("Hello, " + name + "!");
        }
    }

    private static void printTopics(List<String> topics) {
        System.out.println("\nPractice topics:");
        for (int i = 0; i < topics.size(); i++) {
            System.out.println((i + 1) + ". " + topics.get(i));
        }
    }
}
