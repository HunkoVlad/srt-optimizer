import org.testng.Assert;
import org.testng.annotations.Test;

public class SampleTestNGTest {

    @Test
    public void shouldSortArrayListInAscendingOrder() {
        java.util.List<Integer> numbers = new java.util.ArrayList<>();
        numbers.add(3);
        numbers.add(1);
        numbers.add(2);

        java.util.Collections.sort(numbers);

        Assert.assertEquals(numbers, java.util.List.of(1, 2, 3), "ArrayList should be sorted in ascending order");
        System.out.println("Test 'shouldSortArrayListInAscendingOrder' passed");
    }

    @Test(enabled = false)
    public void shouldDetectNonEmptyName() {
        String name = "Volodymyr";

        Assert.assertFalse(name.isBlank(), "Name should not be blank");
        System.out.println("Test 'shouldDetectNonEmptyName' passed");
    }

    private int add(int left, int right) {
        return left + right;
    }
}
